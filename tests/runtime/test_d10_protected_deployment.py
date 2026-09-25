from __future__ import annotations

import ast
import hashlib
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from scripts.build_d10_deployment_identity import D10BuildResult
from scripts.p1242_provision_d10 import provision_sealed_deployment
from scripts.p1243_publish_d10_trust import (
    publish_signed_trust as _publish_signed_trust,
)

from scripts import d10_protected_deployment as d
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_GUARD_RELATIVE_PATH,
    D10_LAUNCHER_RELATIVE_PATH,
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
    parse_deployment_attestation,
    parse_executable_manifest,
)


def _with_builder(root: Path, builder, operation):
    original = d.build_d10_deployment_identity
    d.build_d10_deployment_identity = builder
    try:
        return operation()
    finally:
        d.build_d10_deployment_identity = original


def publish_signed_trust(root, backend, signer, verifier, *, builder):
    return _with_builder(
        root,
        builder,
        lambda: _publish_signed_trust(root, backend, signer, verifier),
    )


def _entry(path: str, data: bytes) -> ExecutableManifestEntry:
    return ExecutableManifestEntry(path, len(data), hashlib.sha256(data).hexdigest())


def _checkout(root: Path) -> dict[str, bytes]:
    files = {
        "src/trading_bot/__init__.py": b"package",
        "src/trading_bot/runtime/data.json": b'{"safe":true}',
        D10_LAUNCHER_RELATIVE_PATH: b"launcher bytes",
        D10_GUARD_RELATIVE_PATH: b"exact guard bytes",
    }
    for name, data in files.items():
        target = root.joinpath(*name.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return files


def _build(files: dict[str, bytes]) -> D10BuildResult:
    entries = tuple(
        sorted(
            (
                _entry(name, data)
                for name, data in files.items()
                if name != D10_GUARD_RELATIVE_PATH
            ),
            key=lambda item: item.relative_path,
        )
    )
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, entries)
    guard = files[D10_GUARD_RELATIVE_PATH]
    attestation = build_deployment_attestation(
        certified_source_head=d.CERTIFIED_SOURCE_HEAD,
        certified_source_tree=d.CERTIFIED_SOURCE_TREE,
        production_python_version=d.PRODUCTION_PYTHON_VERSION,
        launch_guard_byte_length=len(guard),
        launch_guard_sha256=hashlib.sha256(guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(entries),
    )
    return D10BuildResult(
        manifest.canonical_bytes(),
        manifest.digest,
        attestation.canonical_bytes(),
        attestation.deployment_id,
        len(entries),
        d.CERTIFIED_SOURCE_HEAD,
        d.CERTIFIED_SOURCE_TREE,
    )


def _builder(root: Path, expected: dict[str, bytes]):
    result = _build(expected)

    def build(**kwargs):
        assert kwargs == {
            "repository_root": root,
            "expected_head": d.CERTIFIED_SOURCE_HEAD,
            "expected_tree": d.CERTIFIED_SOURCE_TREE,
            "production_python_version": d.PRODUCTION_PYTHON_VERSION,
        }
        return result

    return build


def _native(
    path: str, *, directory: bool, bad: dict[str, str] | None = None, size: int = 0
) -> d.NativeObject:
    owner, protected, aces = d.expected_policy(directory)
    item = d.NativeObject(
        path,
        path,
        directory,
        owner,
        protected,
        aces,
        False,
        3,
        "F:\\",
        "NTFS",
        17,
        int(hashlib.sha256(path.encode()).hexdigest()[:8], 16),
        1,
        size,
    )
    for key, value in (bad or {}).items():
        if key == path:
            if value == "reparse":
                item = replace(item, reparse=True)
            elif value == "hardlink":
                item = replace(item, links=2)
            elif value == "acl":
                item = replace(item, aces=())
            elif value == "owner":
                item = replace(item, owner_sid=d.SYSTEM_SID)
            elif value == "path":
                item = replace(item, final_path=path + r"\redirected")
            elif value == "dacl":
                item = replace(item, dacl_protected=False)
            elif value == "type":
                item = replace(item, directory=not directory)
    return item


class FakeBackend:
    def __init__(self, *, bad: dict[str, str] | None = None):
        self.objects: dict[str, bytes | None] = {d.D10_PARENT: None}
        self.bad = bad or {}
        self.operations: list[tuple[str, str]] = []
        self.corrupt_final: str | None = None
        self.collision_on_publish: str | None = None
        self.source_inventory: tuple[str, ...] = ()

    def require_administrator(self) -> None:
        self.operations.append(("admin", "required"))

    def bind_source_inventory(self, relative_paths: tuple[str, ...]) -> None:
        self.operations.append(("bind_inventory", ",".join(relative_paths)))
        if self.source_inventory and self.source_inventory != relative_paths:
            raise d.DeploymentBlocked("source_inventory_binding_conflict")
        self.source_inventory = relative_paths

    def require_absent(self, path: str) -> None:
        self.operations.append(("absent", path))
        if path in self.objects:
            raise d.DeploymentBlocked("reserved_or_final_path_present")

    def create_directory(self, path: str) -> None:
        self.operations.append(("mkdir", path))
        if path in self.objects or self.objects.get(str(Path(path).parent)) is not None:
            # Windows paths need ntpath semantics; root/staging parent is handled below.
            parent = path.rsplit("\\", 1)[0]
            if self.objects.get(parent, b"missing") is not None:
                raise d.DeploymentBlocked("create_only_directory_failed")
        parent = path.rsplit("\\", 1)[0]
        if (
            parent not in self.objects
            or parent in self.objects
            and self.objects[parent] is not None
        ):
            raise d.DeploymentBlocked("parent_missing_or_not_directory")
        self.objects[path] = None

    def create_file(self, path: str, data: bytes) -> None:
        self.operations.append(("create", path))
        parent = path.rsplit("\\", 1)[0]
        if (
            path in self.objects
            or parent not in self.objects
            or self.objects[parent] is not None
        ):
            raise d.DeploymentBlocked("create_new_file_failed")
        if path == d.D10_ACTIVATION_LEASE or "activation.lease" in path:
            raise AssertionError("activation lease is not a P124-2/P124-3 write target")
        self.objects[path] = data

    def publish_create_only(self, installing_path: str, final_path: str) -> None:
        self.operations.append(("publish", final_path))
        if final_path == self.collision_on_publish:
            self.objects[final_path] = b"concurrent-existing-object"
            self.collision_on_publish = None
        if final_path in self.objects or installing_path not in self.objects:
            raise d.DeploymentBlocked("create_only_atomic_publication_failed")
        is_directory = self.objects[installing_path] is None
        if is_directory:
            source_prefix = installing_path + "\\"
            rows = [
                key
                for key in self.objects
                if key == installing_path or key.startswith(source_prefix)
            ]
            for key in rows:
                new = final_path + key[len(installing_path) :]
                if new in self.objects:
                    raise d.DeploymentBlocked("create_only_atomic_publication_failed")
            for key in sorted(rows, key=len):
                new = final_path + key[len(installing_path) :]
                self.objects[new] = self.objects.pop(key)
        else:
            self.objects[final_path] = self.objects.pop(installing_path)
        if self.corrupt_final == final_path and isinstance(
            self.objects[final_path], bytes
        ):
            self.objects[final_path] = self.objects[final_path] + b"drift"

    def _directory_children(self, path: str) -> tuple[str, ...]:
        prefix = path + "\\"
        result = set()
        for key in self.objects:
            if key.startswith(prefix):
                suffix = key[len(prefix) :]
                if suffix:
                    result.add(suffix.split("\\", 1)[0])
        return tuple(sorted(result))

    def list_directory(self, path: str) -> d.CheckedDirectory:
        self.operations.append(("list", path))
        if path not in self.objects or self.objects[path] is not None:
            raise d.DeploymentBlocked("directory_unavailable")
        identity = _native(path, directory=True, bad=self.bad)
        return d.CheckedDirectory(identity, self._directory_children(path), True)

    def read_file(self, path: str, limit: int) -> d.CheckedFile:
        self.operations.append(("read", path))
        data = self.objects.get(path)
        if type(data) is not bytes or len(data) > limit:
            raise d.DeploymentBlocked("file_unavailable")
        return d.CheckedFile(
            _native(path, directory=False, bad=self.bad, size=len(data)),
            data,
            True,
        )


class FakeSigner:
    def __init__(
        self,
        *,
        identity: d.SigningIdentity | None = None,
        signature: bytes | None = None,
        response: d.DetachedSignature | None = None,
    ):
        self._identity = identity or d.SigningIdentity(
            d.D10_SIGNING_KEY_ID,
            d.SIGNATURE_ALGORITHM,
            d.SIGNATURE_HASH,
            d.SIGNATURE_ENCODING,
            False,
        )
        self.signature = signature or _signature()
        self.response = response
        self.requests: list[d.SigningRequest] = []

    @property
    def identity(self) -> d.SigningIdentity:
        return self._identity

    def sign_digest(self, request: d.SigningRequest) -> d.DetachedSignature:
        self.requests.append(request)
        return self.response or d.DetachedSignature(
            self._identity.key_id,
            self._identity.algorithm,
            self._identity.digest_algorithm,
            self._identity.signature_encoding,
            self.signature,
        )


class FakeVerifier:
    key_id = d.D10_SIGNING_KEY_ID

    def __init__(self, *, valid: bool = True):
        self.valid = valid
        self.calls = 0

    def verify(self, message: bytes, signature: bytes) -> bool:
        self.calls += 1
        return self.valid and len(message) > 0 and signature == _signature()


def _signature() -> bytes:
    return (1).to_bytes(32, "big") + (2).to_bytes(32, "big")


def _prepared(root: Path) -> tuple[dict[str, bytes], object]:
    files = _checkout(root)
    material = d.build_certified_material(root, builder=_builder(root, files))
    return files, material


def _provision(root: Path, backend: FakeBackend, files: dict[str, bytes]):
    return _with_builder(
        root,
        _builder(root, files),
        lambda: provision_sealed_deployment(root, backend),
    )


def test_exact_certified_identity_canonical_artifacts_and_guard_bytes(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    material = d.build_certified_material(tmp_path, builder=_builder(tmp_path, files))
    assert d.CERTIFIED_SOURCE_HEAD == "acee8f80e947bcaefd79fa2c44531e8bbdf4cd0c"
    assert d.CERTIFIED_SOURCE_TREE == "e2850c86adc83b70ab11f6db9e421e8584832c98"
    assert material.build.certified_source_head == d.CERTIFIED_SOURCE_HEAD
    assert material.build.certified_source_tree == d.CERTIFIED_SOURCE_TREE
    assert material.guard_bytes == files[D10_GUARD_RELATIVE_PATH]
    assert (
        parse_executable_manifest(
            material.build.executable_manifest_bytes
        ).canonical_bytes()
        == material.build.executable_manifest_bytes
    )
    assert (
        parse_deployment_attestation(
            material.build.unsigned_deployment_attestation_bytes
        ).canonical_bytes()
        == material.build.unsigned_deployment_attestation_bytes
    )
    assert (
        material.attestation.launch_guard_sha256
        == hashlib.sha256(material.guard_bytes).hexdigest()
    )


@pytest.mark.parametrize("wrong", ["head", "tree"])
def test_wrong_certified_identity_is_rejected(tmp_path: Path, wrong: str) -> None:
    files = _checkout(tmp_path)
    result = _build(files)
    field = "certified_source_head" if wrong == "head" else "certified_source_tree"
    result = replace(result, **{field: "f" * 40})
    with pytest.raises(d.DeploymentBlocked):
        d.build_certified_material(tmp_path, builder=lambda **_: result)


@pytest.mark.parametrize(
    "change",
    ["dirty", "missing", "extra", "case", "git", "cache", "pyc", "pyo", "hardlink"],
)
def test_exact_source_inventory_rejects_dirty_and_unsafe_entries(
    tmp_path: Path, change: str
) -> None:
    files = _checkout(tmp_path)
    target = tmp_path / "src" / "trading_bot"
    if change == "dirty":
        (target / "__init__.py").write_bytes(b"changed")
    elif change == "missing":
        (target / "runtime" / "data.json").unlink()
    elif change == "extra":
        (target / "extra.py").write_bytes(b"extra")
    elif change == "case":
        (target / "__INIT__.py").write_bytes(b"case")
    elif change == "git":
        (target / ".git").mkdir()
    elif change == "cache":
        (target / "__pycache__").mkdir()
    elif change in {"pyc", "pyo"}:
        (target / ("bad." + change)).write_bytes(b"bytecode")
    elif change == "hardlink":
        try:
            os.link(target / "__init__.py", target / "hardlink.py")
        except OSError:
            pytest.skip("filesystem does not permit hard-link fixture")
    with pytest.raises(d.DeploymentBlocked):
        d.build_certified_material(tmp_path, builder=_builder(tmp_path, files))


def test_local_package_walker_rejects_case_collisions_on_any_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = _checkout(tmp_path)
    manifest = parse_executable_manifest(_build(files).executable_manifest_bytes)
    source_root = tmp_path / "src" / "trading_bot"
    monkeypatch.setattr(
        d.os,
        "walk",
        lambda *args, **kwargs: iter([(str(source_root), ["Package", "package"], [])]),
    )
    with pytest.raises(d.DeploymentBlocked, match="source_case_collision"):
        d._inspect_local_package(tmp_path, manifest)


def test_wrong_and_dirty_checkout_are_rejected_by_existing_builder(
    tmp_path: Path,
) -> None:
    root = tmp_path / "git-repo"
    _checkout(root)

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    git("add", "src", "scripts")
    git("commit", "-qm", "fixture")
    head = git("rev-parse", "HEAD")
    tree = git("show", "-s", "--format=%T", "HEAD")
    with pytest.raises(d.DeploymentBlocked):
        d.build_certified_material(root)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(d, "CERTIFIED_SOURCE_HEAD", head)
    monkeypatch.setattr(d, "CERTIFIED_SOURCE_TREE", tree)
    try:
        material = d.build_certified_material(root)
        assert material.build.certified_source_head == head
        (root / "src" / "trading_bot" / "__init__.py").write_bytes(b"dirty")
        with pytest.raises(d.DeploymentBlocked):
            d.build_certified_material(root)
    finally:
        monkeypatch.undo()


def _mock_administrator_backend(
    *,
    elevation: int = 1,
    member: int = 1,
    failure: str | None = None,
):
    import ctypes
    from ctypes import wintypes

    from scripts.d10_protected_deployment_windows import WindowsDeploymentBackend

    backend = object.__new__(WindowsDeploymentBackend)
    backend._kernel = object()
    backend._advapi = object()
    events: list[tuple[object, ...]] = []

    def open_token(process, access, output):
        events.append(("open", process, access))
        if failure == "open":
            return False
        ctypes.cast(output, ctypes.POINTER(wintypes.HANDLE))[0] = 0x5100
        return True

    def get_info(token, info_class, output, size, returned):
        events.append(("elevation", token.value, info_class, size))
        if failure == "information":
            return False
        ctypes.cast(output, ctypes.POINTER(wintypes.DWORD))[0] = elevation
        ctypes.cast(returned, ctypes.POINTER(wintypes.DWORD))[0] = (
            0 if failure == "short_elevation" else ctypes.sizeof(wintypes.DWORD)
        )
        return True

    def duplicate(token, level, output):
        events.append(("duplicate", token.value, level))
        if failure == "duplicate":
            return False
        value = 0x5100 if failure == "aliased_token" else 0x5200
        ctypes.cast(output, ctypes.POINTER(wintypes.HANDLE))[0] = value
        return True

    def convert(sid, output):
        events.append(("sid", sid))
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 0x5300
        return failure != "sid"

    def check(token, sid, output):
        events.append(("membership", token.value, sid.value))
        if failure == "membership":
            return False
        ctypes.cast(output, ctypes.POINTER(wintypes.BOOL))[0] = member
        return True

    def free(sid):
        events.append(("free", sid.value))
        return 0x5300 if failure == "free" else None

    def close(handle):
        events.append(("close", handle.value))
        return failure != "close" or handle.value != 0x5200

    functions = {
        "GetCurrentProcess": lambda: 0x5000,
        "OpenProcessToken": open_token,
        "GetTokenInformation": get_info,
        "DuplicateToken": duplicate,
        "ConvertStringSidToSidW": convert,
        "CheckTokenMembership": check,
        "LocalFree": free,
        "CloseHandle": close,
    }
    backend._bind = lambda _lib, name, _args, _result: functions[name]
    return backend, events


@pytest.mark.parametrize(
    ("elevation", "member", "failure", "allowed"),
    [
        (1, 1, None, True),
        (0, 1, None, False),
        (1, 0, None, False),
        (1, 1, "duplicate", False),
        (1, 1, "membership", False),
        (1, 1, "information", False),
        (1, 1, "short_elevation", False),
        (2, 1, None, False),
        (1, 2, None, False),
        (1, 1, "sid", False),
        (1, 1, "aliased_token", False),
        (1, 1, "free", False),
        (1, 1, "close", False),
        (1, 1, "open", False),
    ],
)
def test_native_administrator_proof_uses_process_primary_and_duplicate_only(
    elevation: int, member: int, failure: str | None, allowed: bool
) -> None:
    backend, events = _mock_administrator_backend(
        elevation=elevation, member=member, failure=failure
    )
    if allowed:
        backend.require_administrator()
    else:
        with pytest.raises(d.DeploymentBlocked):
            backend.require_administrator()

    assert events[0] == ("open", 0x5000, 0x0008 | 0x0002)
    if failure == "open":
        assert events == [("open", 0x5000, 0x0008 | 0x0002)]
        return
    assert ("elevation", 0x5100, 20, 4) in events
    assert events.count(("close", 0x5100)) == 1
    if failure in {"information", "short_elevation"} or elevation == 2:
        assert not any(row[0] == "duplicate" for row in events)
        return
    assert ("duplicate", 0x5100, 2) in events
    if failure == "duplicate":
        assert not any(row[0] == "membership" for row in events)
        return
    if failure == "aliased_token":
        assert events.count(("close", 0x5100)) == 1
        assert not any(row[0] == "membership" for row in events)
        return
    assert events.count(("close", 0x5200)) == 1
    assert events.index(("close", 0x5200)) < events.index(("close", 0x5100))
    assert events.count(("free", 0x5300)) == 1
    if failure == "sid":
        assert not any(row[0] == "membership" for row in events)
    else:
        assert ("membership", 0x5200, 0x5300) in events
        assert ("membership", 0x5100, 0x5300) not in events


def test_native_create_paths_are_fixed_and_manifest_bound() -> None:
    from scripts.d10_protected_deployment_windows import WindowsDeploymentBackend

    backend = object.__new__(WindowsDeploymentBackend)
    backend._source_files = frozenset()
    backend._source_directories = frozenset()
    inventory = (
        D10_LAUNCHER_RELATIVE_PATH,
        "src/trading_bot/__init__.py",
        "src/trading_bot/runtime/data.json",
    )
    inventory = tuple(sorted(inventory))
    backend.bind_source_inventory(inventory)
    assert backend._allowed_directory_create(d.D10_ROOT)
    assert backend._allowed_file_create(
        d.D10_SOURCE_INSTALLING + r"\src\trading_bot\__init__.py"
    )
    assert backend._allowed_file_create(d.D10_GUARD_INSTALLING)
    assert backend._allowed_file_create(d.TRUST_INSTALLING_PATHS[0])
    assert not backend._allowed_file_create(
        d.D10_SOURCE_INSTALLING + r"\src\trading_bot\extra.py"
    )
    assert not backend._allowed_directory_create(
        d.D10_SOURCE_INSTALLING + r"\src\trading_bot\__pycache__"
    )
    assert not backend._allowed_file_create(d.D10_ROOT + r"\activation.lease.json")
    for invalid in (
        "src/trading_bot/../activation.lease.json",
        "src/trading_bot/module.py:stream",
        "src/trading_bot/CON.py",
        "src/trading_bot/.git/config",
        "src/trading_bot/__pycache__/module.pyc",
        "src/trading_bot/module.pyc",
    ):
        candidate = object.__new__(WindowsDeploymentBackend)
        candidate._source_files = frozenset()
        candidate._source_directories = frozenset()
        with pytest.raises(d.DeploymentBlocked):
            candidate.bind_source_inventory(tuple(sorted((*inventory, invalid))))


def test_p1243_v3_signer_and_windows_verifier_identity_agree() -> None:
    from scripts import d10_protected_deployment_windows as windows
    from scripts import d10_signing_key_windows as cng

    signer_identity = cng.WindowsCngExternalSigner().identity
    assert d.D10_SIGNING_KEY_ID == "AITradingBot/D10/DeploymentAttestation/v3"
    assert windows.WindowsCngVerifier.key_id == d.D10_SIGNING_KEY_ID
    d.require_signer_identity(signer_identity)
    with pytest.raises(
        d.DeploymentBlocked, match="signing_identity_or_protocol_mismatch"
    ):
        d.require_signer_identity(
            d.SigningIdentity(
                "AITradingBot/D10/DeploymentAttestation/v2",
                d.SIGNATURE_ALGORITHM,
                d.SIGNATURE_HASH,
                d.SIGNATURE_ENCODING,
                False,
            )
        )


def test_native_policy_matches_frozen_guard_security_and_verification_key() -> None:
    from scripts.d10_protected_deployment_windows import PUBLIC_KEY

    from scripts import run_personal_desktop_d10_launch_guard as guard

    for directory, frozen in (
        (True, guard.DIRECTORY_POLICY),
        (False, guard.FILE_POLICY),
    ):
        owner, protected, aces = d.expected_policy(directory)
        assert owner == frozen.owner
        assert protected is frozen.protected
        assert tuple((a.sid, a.mask, a.ace_type, a.flags) for a in aces) == tuple(
            (a.sid, a.mask, a.ace_type, a.flags) for a in frozen.aces
        )
    assert PUBLIC_KEY == guard.D10_PUBLIC_KEY


def test_final_native_inventory_rejects_missing_extra_case_git_and_bytecode(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    _, material = _prepared(tmp_path)
    cases = {
        "missing": (
            d.D10_SOURCE + r"\src\trading_bot\runtime\data.json",
            None,
        ),
        "extra": (d.D10_SOURCE + r"\src\trading_bot\unexpected.py", b"extra"),
        "case": (d.D10_SOURCE + r"\src\trading_bot\__INIT__.py", b"case"),
        "git": (d.D10_SOURCE + r"\src\trading_bot\.git", None),
        "cache": (d.D10_SOURCE + r"\src\trading_bot\__pycache__", None),
        "bytecode": (d.D10_SOURCE + r"\src\trading_bot\bad.pyc", b"bytecode"),
    }
    for mutation, (path, data) in cases.items():
        backend = FakeBackend()
        _provision(tmp_path, backend, files)
        if mutation == "missing":
            backend.objects.pop(path)
        else:
            backend.objects[path] = data
        with pytest.raises(d.DeploymentBlocked):
            d.verify_provisioned_state(backend, material)


def test_native_directory_inventory_rejects_case_colliding_names() -> None:
    path = d.D10_ROOT
    checked = d.CheckedDirectory(
        _native(path, directory=True), ("source", "Source"), True
    )
    with pytest.raises(d.DeploymentBlocked, match="native_inventory"):
        d.require_directory(checked, path, {"source", "Source"})


def test_p1242_reserved_conflict_blocks_before_root_creation(tmp_path: Path) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    conflict = d.TRUST_INSTALLING_PATHS[0]
    backend.objects[conflict] = b"preexisting"
    with pytest.raises(d.DeploymentBlocked):
        _provision(tmp_path, backend, files)
    assert d.D10_ROOT not in backend.objects
    assert not any(
        op == "mkdir" and path == d.D10_ROOT for op, path in backend.operations
    )


def test_p1242_create_only_exact_manifest_snapshot_and_deterministic_transcript(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    first, second = FakeBackend(), FakeBackend()
    result1 = _provision(tmp_path, first, files)
    result2 = _provision(tmp_path, second, files)
    assert result1.transcript == result2.transcript
    expected_source = {
        d.D10_SOURCE,
        d.D10_SOURCE + r"\src",
        d.D10_SOURCE + r"\src\trading_bot",
        d.D10_SOURCE + r"\src\trading_bot\runtime",
        d.D10_SOURCE + r"\scripts",
    }
    actual_source = {
        path
        for path in first.objects
        if path == d.D10_SOURCE or path.startswith(d.D10_SOURCE + "\\")
    }
    assert actual_source == expected_source | {
        d.D10_SOURCE + "\\" + name.replace("/", "\\")
        for name in files
        if name != D10_GUARD_RELATIVE_PATH
    }
    assert first.objects[d.D10_GUARD] == files[D10_GUARD_RELATIVE_PATH]
    assert first.objects[d.D10_ROOT] is None
    assert set(first._directory_children(d.D10_ROOT)) == {"launch-guard.py", "source"}
    assert not any(
        op == "publish" and path not in {d.D10_GUARD, d.D10_SOURCE}
        for op, path in first.operations
    )
    assert not any(
        "activation.lease" in path or "no-pycache" in path
        for _, path in first.operations
        if _ != "absent"
    )
    assert b'"activation_authority":"NONE"' in result1.transcript
    assert b'"scheduler_authority":"NONE"' in result1.transcript


@pytest.mark.parametrize(
    "drift", ["reparse", "hardlink", "path", "acl", "owner", "dacl", "type"]
)
def test_p1242_final_native_drift_blocks(tmp_path: Path, drift: str) -> None:
    files = _checkout(tmp_path)
    target = d.D10_GUARD if drift != "acl" else d.D10_SOURCE
    backend = FakeBackend(bad={target: drift})
    with pytest.raises(d.DeploymentBlocked):
        _provision(tmp_path, backend, files)


def test_p1242_final_byte_reverification_blocks(tmp_path: Path) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    backend.corrupt_final = d.D10_GUARD
    with pytest.raises(d.DeploymentBlocked, match="final_bytes"):
        _provision(tmp_path, backend, files)


def test_p1242_existing_root_and_installing_conflict_block_without_replacement(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    backend.objects[d.D10_ROOT] = None
    with pytest.raises(d.DeploymentBlocked):
        _provision(tmp_path, backend, files)
    assert not any(op == "publish" for op, _ in backend.operations)


def test_p1243_publishes_only_canonical_trust_bytes_and_verifies_signature(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    backend, signer, verifier = FakeBackend(), FakeSigner(), FakeVerifier()
    _provision(tmp_path, backend, files)
    result = publish_signed_trust(
        tmp_path, backend, signer, verifier, builder=_builder(tmp_path, files)
    )
    assert (
        backend.objects[d.D10_ATTESTATION]
        == _build(files).unsigned_deployment_attestation_bytes
    )
    assert backend.objects[d.D10_MANIFEST] == _build(files).executable_manifest_bytes
    assert backend.objects[d.D10_SIGNATURE] == _signature()
    assert verifier.calls >= 2
    assert len(signer.requests) == 1
    request = signer.requests[0]
    assert request.key_id == d.D10_SIGNING_KEY_ID
    assert (
        request.message_sha256
        == hashlib.sha256(backend.objects[d.D10_ATTESTATION]).digest()
    )
    assert set(backend._directory_children(d.D10_ROOT)) == {
        "launch-guard.py",
        "source",
        "deployment.attestation.json",
        "deployment.attestation.sig",
        "executable-manifest.json",
    }
    assert result.transcript == d.operation_transcript(
        "P124-3",
        d.build_certified_material(tmp_path, builder=_builder(tmp_path, files)),
        paths=d.TRUST_FINAL_PATHS,
        signature=_signature(),
    )


@pytest.mark.parametrize(
    "identity",
    [
        d.SigningIdentity(
            "wrong/key",
            d.SIGNATURE_ALGORITHM,
            d.SIGNATURE_HASH,
            d.SIGNATURE_ENCODING,
            False,
        ),
        d.SigningIdentity(
            d.D10_SIGNING_KEY_ID, "RSA", d.SIGNATURE_HASH, d.SIGNATURE_ENCODING, False
        ),
        d.SigningIdentity(
            d.D10_SIGNING_KEY_ID,
            d.SIGNATURE_ALGORITHM,
            "SHA-384",
            d.SIGNATURE_ENCODING,
            False,
        ),
        d.SigningIdentity(
            d.D10_SIGNING_KEY_ID, d.SIGNATURE_ALGORITHM, d.SIGNATURE_HASH, "DER", False
        ),
        d.SigningIdentity(
            d.D10_SIGNING_KEY_ID,
            d.SIGNATURE_ALGORITHM,
            d.SIGNATURE_HASH,
            d.SIGNATURE_ENCODING,
            True,
        ),
    ],
)
def test_p1243_wrong_key_or_protocol_blocks_before_signing(
    tmp_path: Path, identity: d.SigningIdentity
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    signer, verifier = FakeSigner(identity=identity), FakeVerifier()
    with pytest.raises(d.DeploymentBlocked):
        publish_signed_trust(
            tmp_path, backend, signer, verifier, builder=_builder(tmp_path, files)
        )
    assert signer.requests == []
    assert not any(
        op == "create" and path in d.TRUST_INSTALLING_PATHS
        for op, path in backend.operations
    )


@pytest.mark.parametrize(
    "response",
    [
        d.DetachedSignature(
            "wrong/key",
            d.SIGNATURE_ALGORITHM,
            d.SIGNATURE_HASH,
            d.SIGNATURE_ENCODING,
            _signature(),
        ),
        d.DetachedSignature(
            d.D10_SIGNING_KEY_ID,
            "RSA",
            d.SIGNATURE_HASH,
            d.SIGNATURE_ENCODING,
            _signature(),
        ),
        d.DetachedSignature(
            d.D10_SIGNING_KEY_ID,
            d.SIGNATURE_ALGORITHM,
            d.SIGNATURE_HASH,
            "DER",
            _signature(),
        ),
    ],
)
def test_p1243_wrong_returned_signing_identity_blocks_before_publication(
    tmp_path: Path, response: d.DetachedSignature
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    signer = FakeSigner(response=response)
    with pytest.raises(d.DeploymentBlocked, match="signed_response"):
        publish_signed_trust(
            tmp_path, backend, signer, FakeVerifier(), builder=_builder(tmp_path, files)
        )
    assert len(signer.requests) == 1
    assert not any(path in d.TRUST_FINAL_PATHS for path in backend.objects)


def test_p1243_rebuild_after_external_signing_blocks_source_drift(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    target = tmp_path / "src" / "trading_bot" / "__init__.py"

    class MutatingSigner(FakeSigner):
        def sign_digest(self, request: d.SigningRequest) -> d.DetachedSignature:
            result = super().sign_digest(request)
            target.write_bytes(b"source changed while signing")
            return result

    signer = MutatingSigner()
    with pytest.raises(d.DeploymentBlocked, match="source_bytes_differ"):
        publish_signed_trust(
            tmp_path, backend, signer, FakeVerifier(), builder=_builder(tmp_path, files)
        )
    assert len(signer.requests) == 1
    assert not any(path in d.TRUST_FINAL_PATHS for path in backend.objects)
    assert not any(
        path in d.TRUST_INSTALLING_PATHS
        for operation, path in backend.operations
        if operation == "create"
    )


def test_p1243_wrong_verifier_key_blocks_before_signing(tmp_path: Path) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    verifier = FakeVerifier()
    verifier.key_id = "wrong/key"
    signer = FakeSigner()
    with pytest.raises(d.DeploymentBlocked, match="signature_verifier_key"):
        publish_signed_trust(
            tmp_path, backend, signer, verifier, builder=_builder(tmp_path, files)
        )
    assert signer.requests == []


def test_p1243_create_only_publish_refuses_concurrent_final_object(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    backend.collision_on_publish = d.D10_MANIFEST
    with pytest.raises(d.DeploymentBlocked, match="create_only_atomic_publication"):
        publish_signed_trust(
            tmp_path,
            backend,
            FakeSigner(),
            FakeVerifier(),
            builder=_builder(tmp_path, files),
        )
    assert backend.objects[d.D10_MANIFEST] == b"concurrent-existing-object"


def test_p1243_final_trust_byte_reverification_blocks(tmp_path: Path) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    backend.corrupt_final = d.D10_MANIFEST
    with pytest.raises(
        d.DeploymentBlocked, match="file_unavailable|final_bytes|native_read_size"
    ):
        publish_signed_trust(
            tmp_path,
            backend,
            FakeSigner(),
            FakeVerifier(),
            builder=_builder(tmp_path, files),
        )


@pytest.mark.parametrize(
    "signature,valid",
    [
        (b"x" * 63, True),
        (b"\x00" * 64, True),
        (_signature(), False),
    ],
)
def test_p1243_invalid_or_noncanonical_signature_blocks_before_publication(
    tmp_path: Path, signature: bytes, valid: bool
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    published_before = sum(op == "publish" for op, _ in backend.operations)
    signer, verifier = FakeSigner(signature=signature), FakeVerifier(valid=valid)
    with pytest.raises(d.DeploymentBlocked):
        publish_signed_trust(
            tmp_path, backend, signer, verifier, builder=_builder(tmp_path, files)
        )
    assert sum(op == "publish" for op, _ in backend.operations) == published_before
    assert not any(path in d.TRUST_FINAL_PATHS for path in backend.objects)


@pytest.mark.parametrize(
    "conflict", ["final", "installing", "partial-source", "lease", "cache"]
)
def test_p1243_conflicting_or_partial_state_blocks_and_never_replaces(
    tmp_path: Path, conflict: str
) -> None:
    files = _checkout(tmp_path)
    backend = FakeBackend()
    _provision(tmp_path, backend, files)
    if conflict == "final":
        backend.objects[d.D10_MANIFEST] = b"preexisting"
    elif conflict == "installing":
        backend.objects[d.TRUST_INSTALLING_PATHS[0]] = b"partial"
    elif conflict == "partial-source":
        backend.objects[d.D10_ROOT + r"\source.installing"] = None
    elif conflict == "lease":
        backend.objects[d.D10_ACTIVATION_LEASE] = b"lease"
    else:
        backend.objects[d.D10_CACHE_PREFIX] = None
    signer = FakeSigner()
    with pytest.raises(d.DeploymentBlocked):
        publish_signed_trust(
            tmp_path, backend, signer, FakeVerifier(), builder=_builder(tmp_path, files)
        )
    assert signer.requests == []
    if conflict == "final":
        assert backend.objects[d.D10_MANIFEST] == b"preexisting"


def test_transcripts_and_signing_boundary_do_not_leak_secrets_or_capabilities(
    tmp_path: Path,
) -> None:
    files = _checkout(tmp_path)
    backend, signer, verifier = FakeBackend(), FakeSigner(), FakeVerifier()
    _provision(tmp_path, backend, files)
    result = publish_signed_trust(
        tmp_path, backend, signer, verifier, builder=_builder(tmp_path, files)
    )
    lowered = result.transcript.lower()
    for forbidden in (
        b"private_key",
        b"credential",
        b"password",
        b"handle",
        b"token_value",
    ):
        assert forbidden not in lowered
    assert _signature() not in result.transcript
    assert len(signer.requests[0].message_sha256) == 32
    assert tuple(d.SigningRequest.__dataclass_fields__) == (
        "key_id",
        "algorithm",
        "digest_algorithm",
        "signature_encoding",
        "message_sha256",
    )
    assert not any(
        operation == "create" and ("activation.lease" in path or "no-pycache" in path)
        for operation, path in backend.operations
    )


def test_preparation_tools_have_no_scheduler_or_trading_effect_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "scripts" / "d10_protected_deployment.py",
        root / "scripts" / "d10_protected_deployment_windows.py",
        root / "scripts" / "p1242_provision_d10.py",
        root / "scripts" / "p1243_publish_d10_trust.py",
    )
    forbidden = (
        "activation_lease",
        "task_scheduler",
        "market_data",
        "provider",
        "settlement",
        "broker",
        "live_trading",
        "portfolio",
        "order_execution",
        "d10_python_substrate_windows",
        "run_personal_desktop_d10_launch_guard",
    )
    imports = []
    trees = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        trees[path.name] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    assert not any(
        denied in module.casefold() for module in imports for denied in forbidden
    )
