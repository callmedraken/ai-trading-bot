"""133-AC logical fake-native images only; no production path is observed."""

import ast
import ctypes
import hashlib
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import (
    LAUNCHER_RELATIVE_PATH,
    ReleaseInventoryEntry,
    ReleaseManifest,
    installer,
    native_read,
    native_write,
    observer,
)
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseBundle,
    ReleaseFile,
    verify_release_bundle,
)
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstallDisposition,
    InstallReason,
    InstallStatus,
    ObjectFacts,
    ReleasePaths,
)
from trading_bot.supervised_release.model import (
    DURABLE_DATA_ROOT,
    PRODUCTION_PYTHON,
    RELEASES_BASE,
    STRATEGY_ID,
)

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-release-installation"
FAKE_PYTHON = b"inert fake of the separately pinned production Python binary"


def accepted():
    material = {
        "pyproject.toml": b"[project]\nname='fake'\n",
        LAUNCHER_RELATIVE_PATH: b"# inert launcher\n",
        "src/trading_bot/__init__.py": b"# inert package\n",
        "src/trading_bot/nested/model.py": b"# inert model\n",
        "src/trading_bot/runtime/example.py": b"# inert runtime source\n",
    }
    manifest = ReleaseManifest(
        source_head="a" * 40,
        source_tree="b" * 40,
        production_python_version=PYTHON_VERSION,
        production_python_sha256=PYTHON_SHA256,
        launcher_relative_path=LAUNCHER_RELATIVE_PATH,
        launcher_sha256=hashlib.sha256(material[LAUNCHER_RELATIVE_PATH]).hexdigest(),
        source_inventory=tuple(
            ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest())
            for name, data in sorted(material.items())
        ),
        strategy_id=STRATEGY_ID,
        strategy_version="1.0.0",
        strategy_config=MovingAverageCrossoverConfig(5, 20, Decimal("1")),
        risk_policy_id="reviewed-policy",
        risk_policy_version="1.0.0",
        risk_policy_sha256="d" * 64,
    )
    material["manifest.json"] = manifest.to_json().encode()
    bundle = ReleaseBundle(
        tuple(ReleaseFile(name, data) for name, data in sorted(material.items()))
    )
    return verify_release_bundle(
        bundle,
        expected_manifest_sha256=hashlib.sha256(material["manifest.json"]).hexdigest(),
        expected_source_head=manifest.source_head,
        expected_source_tree=manifest.source_tree,
        expected_source_paths=tuple(
            sorted(name for name in material if name != "manifest.json")
        ),
    )


class FakeNative:
    """Store only fixed logical paths, no os/Path/native production observation."""

    def __init__(self, release):
        self.paths = ReleasePaths(release.manifest.release_id)
        self.nodes = {}
        self.data = {}
        self.events = []
        self.counter = 10
        self.fail = None
        self.read_scopes = 0
        self.hook = None
        self.version = PYTHON_VERSION
        for path in (*ANCESTORS, r"F:\AITradingBot\runtime"):
            self.add(path, directory=True)
        self.add(PRODUCTION_PYTHON, directory=False, data=FAKE_PYTHON)

    def add(self, path, *, directory, data=b""):
        self.counter += 1
        self.nodes[path] = ObjectFacts(
            path,
            "directory" if directory else "file",
            (7, self.counter),
            ADMINISTRATORS_SID,
            True,
            IMAGE_ACES,
            size=len(data),
        )
        if not directory:
            self.data[path] = data

    def event(self, phase, path=None):
        if path is not None:
            self.paths.admit(path)
        self.events.append((phase, path))
        if phase == self.fail:
            raise RuntimeError("private unrelated state must never leak")

    def require_administrator_host(self):
        self.event("host")

    @contextmanager
    def install_session(self, paths):
        assert paths == self.paths
        self.event("install_open")
        yield self
        self.event("install_close")

    @contextmanager
    def read_session(self, paths):
        assert paths == self.paths
        self.read_scopes += 1
        self.event("read_open")
        if self.hook:
            self.hook(self, self.read_scopes)
        yield self
        self.event("read_close")

    def object(self, path, *, directory):
        self.event("object", path)
        return self.nodes.get(path)

    def names(self, path):
        self.event("names", path)
        prefix = path + "\\"
        return tuple(
            name[len(prefix) :]
            for name in self.nodes
            if name.startswith(prefix) and "\\" not in name[len(prefix) :]
        )

    def read(self, path, limit):
        self.event("read", path)
        data = self.data[path]
        assert len(data) <= limit
        return data

    def python_version(self):
        self.event("python_version", PRODUCTION_PYTHON)
        return self.version

    def create_directory(self, path):
        assert path == self.paths.staging or path.startswith(self.paths.staging + "\\")
        assert path not in self.nodes
        self.add(path, directory=True)
        self.event("create_directory", path)

    def write_file(self, path, data):
        assert path.startswith(self.paths.staging + "\\")
        assert path not in self.nodes
        self.add(path, directory=False)
        self.event("file_create", path)
        self.data[path] = data
        self.nodes[path] = replace(self.nodes[path], size=len(data))
        self.event("write", path)
        self.event("flush", path)
        self.event("close", path)

    def seal_staging(self):
        self.event("seal_staging")

    def publish(self, staging_identity):
        assert self.nodes[self.paths.staging].identity == staging_identity
        self.event("publish")
        assert self.paths.final not in self.nodes
        for path in tuple(self.nodes):
            if path == self.paths.staging or path.startswith(self.paths.staging + "\\"):
                destination = self.paths.final + path[len(self.paths.staging) :]
                self.nodes[destination] = replace(
                    self.nodes.pop(path), path=destination
                )
                if path in self.data:
                    self.data[destination] = self.data.pop(path)
        self.event("published")
        return True

    def seed(self, release, *, staging=False):
        root = self.paths.staging if staging else self.paths.final
        self.add(root, directory=True)
        for item in release.bundle.files:
            path = self.paths.child(root, item.relative_path)
            parts = path.split("\\")
            for index in range(4, len(parts)):
                directory = "\\".join(parts[:index])
                if directory not in self.nodes:
                    self.add(directory, directory=True)
            self.add(path, directory=False, data=item.data)


@pytest.fixture
def environment(monkeypatch):
    release = accepted()
    native = FakeNative(release)
    # Simulate the pinned executable digest for inert test bytes. All other
    # bytes use real SHA-256; changed Python bytes still fail. No real substrate.
    monkeypatch.setattr(
        observer,
        "hashlib",
        SimpleNamespace(
            sha256=lambda data: (
                SimpleNamespace(hexdigest=lambda: PYTHON_SHA256)
                if data == FAKE_PYTHON
                else hashlib.sha256(data)
            )
        ),
    )
    return release, RuntimeBinding(release), native


def effect_events(native):
    return [
        event
        for event in native.events
        if event[0]
        in {
            "create_directory",
            "file_create",
            "write",
            "flush",
            "close",
            "publish",
            "published",
        }
    ]


def test_fresh_install_independent_replays_and_single_publication(
    environment, monkeypatch
):
    release, binding, native = environment
    replay = observer.verify_release_bundle
    bundles = []

    def recording(bundle, **pins):
        bundles.append(bundle)
        return replay(bundle, **pins)

    monkeypatch.setattr(observer, "verify_release_bundle", recording)
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INSTALLED_VERIFIED
    assert result.disposition is InstallDisposition.VERIFIED
    assert result.reason is InstallReason.VERIFIED
    assert result.evidence.release_id == release.manifest.release_id
    assert result.evidence.manifest_sha256 == release.expected_manifest_sha256
    assert result.evidence.binding_sha256 == binding.sha256
    assert result.evidence.dependency_closure == "UNPROVEN"
    assert native.read_scopes == 2
    assert (
        len(bundles) == 5
    )  # input + staging input/reconstruction + final input/reconstruction
    assert bundles[2] is not release.bundle and bundles[4] is not release.bundle
    assert [phase for phase, _ in native.events].count("publish") == 1
    publication = next(
        i for i, event in enumerate(native.events) if event[0] == "publish"
    )
    assert all(
        path.startswith(native.paths.staging)
        for phase, path in native.events[:publication]
        if phase in {"create_directory", "file_create", "write", "flush", "close"}
    )
    assert native.paths.staging not in native.nodes
    for item in release.bundle.files:
        assert (
            native.data[native.paths.child(native.paths.final, item.relative_path)]
            == item.data
        )
    with pytest.raises(FrozenInstanceError):
        result.evidence.release_id = "bad"
    before = dict(native.nodes), dict(native.data)
    second = installer.install_release(release, binding, native=native)
    assert second.status is InstallStatus.ALREADY_INSTALLED_VERIFIED
    assert second.evidence == result.evidence
    assert (native.nodes, native.data) == before
    assert [phase for phase, _ in native.events].count("publish") == 1


def test_preexisting_exact_final_ignores_existing_staging_without_mutation(environment):
    release, binding, native = environment
    native.seed(release)
    native.seed(release, staging=True)
    before = dict(native.nodes), dict(native.data)
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.ALREADY_INSTALLED_VERIFIED
    assert not effect_events(native)
    assert before == (native.nodes, native.data)


@pytest.mark.parametrize("conflict", ["final", "staging"])
def test_conflicting_roots_block_without_effect(environment, conflict):
    release, binding, native = environment
    native.add(
        native.paths.final if conflict == "final" else native.paths.staging,
        directory=True,
    )
    before = dict(native.nodes), dict(native.data)
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.BLOCKED
    assert result.disposition is InstallDisposition.NO_INSTALLATION_EFFECT
    assert result.reason is (
        InstallReason.FINAL_CONFLICT
        if conflict == "final"
        else InstallReason.STAGING_EXISTS
    )
    assert not effect_events(native)
    assert before == (native.nodes, native.data)


@pytest.mark.parametrize("phase", ["host", "install_open", "object"])
def test_pre_mutation_observation_failures_block(environment, phase):
    release, binding, native = environment
    native.fail = phase
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.BLOCKED
    assert not effect_events(native)
    assert result.evidence is None
    assert "private" not in repr(result)


@pytest.mark.parametrize(
    "phase",
    [
        "create_directory",
        "file_create",
        "write",
        "flush",
        "close",
        "seal_staging",
        "read_open",
        "read",
        "names",
        "read_close",
        "publish",
        "published",
        "install_close",
    ],
)
def test_post_mutation_failures_preserve_all_evidence_without_compensation(
    environment, phase
):
    release, binding, native = environment
    native.fail = phase
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INDETERMINATE
    assert (
        result.disposition is InstallDisposition.PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY
    )
    assert result.evidence is None
    assert native.paths.staging in native.nodes or native.paths.final in native.nodes
    assert len([event for event in native.events if event[0] == phase]) == 1
    assert len([event for event in native.events if event[0] == "publish"]) <= 1
    assert not any(
        phase in {"delete", "cleanup", "repair", "rollback", "retry", "overwrite"}
        for phase, _ in native.events
    )
    assert "private" not in repr(result)
    snapshot = dict(native.nodes), dict(native.data)
    native.fail = None
    prior_effects = list(effect_events(native))
    repeated = installer.install_release(release, binding, native=native)
    assert repeated.status in {
        InstallStatus.BLOCKED,
        InstallStatus.ALREADY_INSTALLED_VERIFIED,
    }
    assert (native.nodes, native.data) == snapshot
    assert effect_events(native) == prior_effects


@pytest.mark.parametrize("completion", [False, None, "success", 1])
def test_ambiguous_publication_preserves_staging(environment, monkeypatch, completion):
    release, binding, native = environment
    calls = []

    def publish(identity):
        calls.append(identity)
        return completion

    monkeypatch.setattr(native, "publish", publish)
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INDETERMINATE
    assert result.reason is InstallReason.PUBLICATION
    assert len(calls) == 1
    assert (
        native.paths.staging in native.nodes and native.paths.final not in native.nodes
    )


def test_published_image_failing_final_observation_is_preserved(environment):
    release, binding, native = environment

    def hook(backend, scope):
        if scope == 2:
            path = backend.paths.child(backend.paths.final, "pyproject.toml")
            backend.data[path] = b"tampered"

    native.hook = hook
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INDETERMINATE
    assert result.reason is InstallReason.FINAL_VERIFICATION
    assert (
        native.paths.final in native.nodes and native.paths.staging not in native.nodes
    )
    assert (
        native.data[native.paths.child(native.paths.final, "pyproject.toml")]
        == b"tampered"
    )


@pytest.mark.parametrize(
    "root",
    ["parent", "container", "drive", "image", "directory", "file", "runtime", "python"],
)
@pytest.mark.parametrize(
    "drift", ["reparse", "type", "filesystem", "volume", "links", "path"]
)
def test_observer_rejects_object_drift_at_every_boundary(environment, root, drift):
    release, binding, native = environment
    native.seed(release)
    path = {
        "parent": RELEASES_BASE,
        "container": ANCESTORS[1],
        "drive": ANCESTORS[0],
        "image": native.paths.final,
        "directory": native.paths.child(native.paths.final, "src"),
        "file": native.paths.child(native.paths.final, "pyproject.toml"),
        "runtime": r"F:\AITradingBot\runtime",
        "python": PRODUCTION_PYTHON,
    }[root]
    original = native.nodes[path]
    change = {
        "reparse": {"reparse": True},
        "type": {"kind": "other"},
        "filesystem": {"filesystem": "FAT32"},
        "volume": {"identity": (9, original.identity[1])},
        "links": {"links": 2},
        "path": {"path": path.lower()},
    }[drift]
    # A changed drive volume must conflict with the next ancestor.
    if drift == "path" and path == "F:\\":
        change = {"path": "f:\\"}
    native.nodes[path] = replace(original, **change)
    with pytest.raises(ValueError):
        observer.observe_installed_release(release, binding, native=native)
    assert not effect_events(native)


@pytest.mark.parametrize("root", ["parent", "image", "directory", "file"])
@pytest.mark.parametrize(
    "change",
    [
        {"owner": TRADING_SID},
        {"protected": False},
        {"aces": ()},
        {"local": False},
        {"persistent_acls": False},
        {"aces": IMAGE_ACES + ((TRADING_SID, 0x1F01FF, 0, 0),)},
        {"aces": IMAGE_ACES[:2] + ((TRADING_SID, 0x1301BF, 0, 0),)},
    ],
)
def test_exact_security_and_read_execute_only_policy(environment, root, change):
    release, binding, native = environment
    native.seed(release)
    path = {
        "parent": RELEASES_BASE,
        "image": native.paths.final,
        "directory": native.paths.child(native.paths.final, "src"),
        "file": native.paths.child(native.paths.final, "pyproject.toml"),
    }[root]
    native.nodes[path] = replace(native.nodes[path], **change)
    with pytest.raises(ValueError):
        observer.observe_installed_release(release, binding, native=native)
    assert IMAGE_ACES[2] == (TRADING_SID, 0x1200A9, 0, 0)
    assert not IMAGE_ACES[2][1] & (
        0x2 | 0x4 | 0x10 | 0x40 | 0x10000 | 0x40000 | 0x80000
    )


def test_volume_boundary_allows_unrelated_rights_but_not_namespace_authority(
    environment,
):
    release, binding, native = environment
    native.seed(release)
    volume = ANCESTORS[0]
    original = native.nodes[volume]
    safe = (
        ("S-1-5-11", 0x00000006, 0, 0),
        ("S-1-3-0", 0x10000000, 0, 0x0B),
    )
    native.nodes[volume] = replace(
        original,
        owner=SYSTEM_SID,
        protected=False,
        aces=safe,
    )
    observer.observe_installed_release(release, binding, native=native)
    native.nodes[volume] = replace(
        native.nodes[volume],
        aces=(("S-1-5-11", 0x000C0040, 0, 0),),
    )
    with pytest.raises(ValueError, match="volume namespace authority rejected"):
        observer.observe_installed_release(release, binding, native=native)


def test_runtime_host_observation_accepts_administrators_or_system_owner(environment):
    release, binding, native = environment
    native.seed(release)
    runtime = r"F:\AITradingBot\runtime"
    native.nodes[runtime] = replace(native.nodes[runtime], owner=SYSTEM_SID)
    native.nodes[PRODUCTION_PYTHON] = replace(
        native.nodes[PRODUCTION_PYTHON], owner=SYSTEM_SID
    )
    observer.observe_installed_release(release, binding, native=native)


@pytest.mark.parametrize(
    "drift",
    [
        "missing_file",
        "extra_file",
        "case_alias",
        "wrong_case",
        "extra_directory",
        "missing_directory",
        "bytes",
        "manifest",
        "file_identity_alias",
    ],
)
def test_observer_reconstructs_exact_namespace_and_bytes(environment, drift):
    release, binding, native = environment
    native.seed(release)
    root = native.paths.final
    file = native.paths.child(root, "pyproject.toml")
    if drift == "missing_file":
        native.nodes.pop(file)
    elif drift == "extra_file":
        native.add(native.paths.child(root, "extra.py"), directory=False)
    elif drift == "case_alias":
        native.add(native.paths.child(root, "PYPROJECT.toml"), directory=False)
    elif drift == "wrong_case":
        native.nodes[file.upper()] = native.nodes.pop(file)
    elif drift == "extra_directory":
        native.add(native.paths.child(root, "extra"), directory=True)
    elif drift == "missing_directory":
        native.nodes.pop(native.paths.child(root, "src"))
    elif drift == "bytes":
        native.data[file] = native.data[file].replace(b"fake", b"evil")
    elif drift == "manifest":
        native.data[native.paths.child(root, "manifest.json")] += b"\n"
    elif drift == "file_identity_alias":
        native.nodes[file] = replace(
            native.nodes[file], identity=native.nodes[root].identity
        )
    with pytest.raises(ValueError):
        observer.observe_installed_release(release, binding, native=native)
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.BLOCKED
    assert not effect_events(native)


@pytest.mark.parametrize(
    "field",
    [
        "expected_manifest_sha256",
        "expected_source_head",
        "expected_source_tree",
        "expected_source_paths",
    ],
)
def test_accepted_release_replayed_before_host_observation(environment, field):
    release, binding, native = environment
    broken = object.__new__(type(release))
    for attribute in (
        "bundle",
        "expected_manifest_sha256",
        "expected_source_head",
        "expected_source_tree",
        "expected_source_paths",
    ):
        object.__setattr__(broken, attribute, getattr(release, attribute))
    object.__setattr__(
        broken,
        field,
        () if field == "expected_source_paths" else "0" * len(getattr(release, field)),
    )
    result = installer.install_release(broken, binding, native=native)
    assert (
        result.status is InstallStatus.BLOCKED and result.reason is InstallReason.INPUT
    )
    assert native.events == []


def test_runtime_binding_mismatch_rejected_before_native_observation(environment):
    release, _, native = environment
    other = accepted()
    object.__setattr__(other, "expected_source_head", "e" * 40)
    result = installer.install_release(release, RuntimeBinding(other), native=native)
    assert result.status is InstallStatus.BLOCKED and native.events == []


@pytest.mark.parametrize("input_kind", [None, object(), "raw"])
def test_untyped_input_rejected_before_host_observation(environment, input_kind):
    release, binding, native = environment
    assert (
        installer.install_release(input_kind, binding, native=native).status
        is InstallStatus.BLOCKED
    )
    assert (
        installer.install_release(release, input_kind, native=native).status
        is InstallStatus.BLOCKED
    )
    assert not native.events


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AI\temp\arch133y-rename-qualification",
        r"F:\AI\temp\arch133z-rename-qualification\child",
        r"f:\ai\TEMP\ARCH133Y-rename-qualification\file",
        r"F:\AITradingBot\Arch133",
        r"C:\AITradingBot\releases",
        r"\\server\share",
        r"\\?\F:\AITradingBot\releases",
        r"F:\AITradingBot\releases\..\Arch133",
        r"F:/AITradingBot/releases",
        "F:\\AITradingBot\\releases\\",
    ],
)
def test_lexical_exclusion_precedes_first_native_observation(
    environment, path, monkeypatch
):
    _, _, native = environment
    calls = []
    session = object.__new__(native_read.WindowsReadSession)
    session.paths, session.handles = native.paths, {}
    monkeypatch.setattr(
        native_read,
        "bind",
        lambda *args: calls.append(args) or pytest.fail("native called"),
    )
    with pytest.raises(ValueError):
        session.open_object(path, directory=True)
    assert not calls and not native.events


@pytest.mark.parametrize(
    "name",
    [
        "../file",
        "./file",
        "/file",
        "F:/file",
        "a/../../file",
        "a//file",
        "a:stream",
        "CON",
        "file.",
        "file ",
        "a\\..\\file",
        "a\x00b",
    ],
)
def test_child_alias_attempts_rejected(environment, name):
    _, _, native = environment
    with pytest.raises(ValueError):
        native.paths.child(native.paths.final, name)
    assert not native.events


def test_child_admits_supported_runtime_source_subtree(environment):
    _, _, native = environment
    root = native.paths.final
    assert native.paths.child(root, "src/trading_bot/runtime") == (
        root + r"\src\trading_bot\runtime"
    )
    assert native.paths.child(root, "src/trading_bot/runtime/example.py") == (
        root + r"\src\trading_bot\runtime\example.py"
    )
    assert not native.events


@pytest.mark.parametrize("which", ["staging", "final"])
@pytest.mark.parametrize("drift", ["reparse", "type", "owner", "volume"])
def test_created_staging_or_final_observer_failure_is_indeterminate(
    environment, which, drift
):
    release, binding, native = environment

    def hook(backend, scope):
        if scope == (1 if which == "staging" else 2):
            path = backend.paths.staging if which == "staging" else backend.paths.final
            fact = backend.nodes[path]
            change = {
                "reparse": {"reparse": True},
                "type": {"kind": "file"},
                "owner": {"owner": TRADING_SID},
                "volume": {"identity": (99, fact.identity[1])},
            }[drift]
            backend.nodes[path] = replace(fact, **change)

    native.hook = hook
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INDETERMINATE
    assert result.reason is (
        InstallReason.STAGING_VERIFICATION
        if which == "staging"
        else InstallReason.FINAL_VERIFICATION
    )
    assert (
        native.paths.staging if which == "staging" else native.paths.final
    ) in native.nodes


@pytest.mark.parametrize("drift", ["hash", "version", "missing", "namespace_separate"])
def test_python_is_separate_host_observation(environment, drift):
    release, binding, native = environment
    native.seed(release)
    if drift == "hash":
        native.data[PRODUCTION_PYTHON] = b"other bytes"
    elif drift == "version":
        native.version = "3.14.4"
    elif drift == "missing":
        native.nodes.pop(PRODUCTION_PYTHON)
    else:
        native.nodes[PRODUCTION_PYTHON] = replace(
            native.nodes[PRODUCTION_PYTHON], path=DURABLE_DATA_ROOT
        )
    with pytest.raises(ValueError):
        observer.observe_installed_release(release, binding, native=native)
    assert not effect_events(native)
    assert not any(
        path and path.startswith(DURABLE_DATA_ROOT) for _, path in native.events
    )


def test_observer_ignores_installer_result_and_reopens_image(environment):
    release, binding, native = environment
    result = installer.install_release(release, binding, native=native)
    before = list(effect_events(native))
    native.data[native.paths.child(native.paths.final, "pyproject.toml")] = b"changed"
    assert result.status is InstallStatus.INSTALLED_VERIFIED
    with pytest.raises(ValueError):
        observer.observe_installed_release(release, binding, native=native)
    assert native.read_scopes == 3 and effect_events(native) == before


def test_native_publication_uses_exact_no_replace_relative_name_and_one_call(
    environment, monkeypatch
):
    release, _, native = environment
    native.seed(release, staging=True)
    session = object.__new__(native_write.WindowsWriteSession)
    session.paths, session.kernel = native.paths, object()
    session.handles = {RELEASES_BASE: 17, native.paths.staging: 19}
    monkeypatch.setattr(session, "object", native.object)
    calls, closes = [], []

    def publish(handle, info_class, buffer, size):
        raw = buffer.raw
        assert handle == 19 and info_class == 3
        assert raw[0] == 0
        assert int.from_bytes(raw[8:16], "little") == 17
        assert int.from_bytes(raw[16:20], "little") == len(
            native.paths.release_id.encode("utf-16-le")
        )
        assert raw[20:size].decode("utf-16-le") == native.paths.release_id
        calls.append((handle, info_class))
        return 1

    monkeypatch.setattr(native_write, "bind", lambda *args: publish)
    monkeypatch.setattr(
        native_write,
        "close_native_handle",
        lambda kernel, handle: closes.append(handle),
    )
    assert session.publish(native.nodes[native.paths.staging].identity) is True
    assert calls == [(19, 3)] and closes == [19]


@pytest.mark.parametrize(
    "which",
    [
        "observer.py",
        "installation_contract.py",
        "installer.py",
        "native_read.py",
        "native_write.py",
    ],
)
def test_capability_separation_and_no_other_effect_imports(which):
    tree = ast.parse(
        (ROOT / "src/trading_bot/supervised_release" / which).read_text(
            encoding="utf-8-sig"
        )
    )
    forbidden_calls = {
        "unlink",
        "rmtree",
        "remove",
        "rename",
        "sleep",
        "run",
        "Popen",
        "exec",
        "eval",
        "__import__",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not any(
                word in (node.module or "").lower()
                for word in (
                    "provider",
                    "oauth",
                    "scheduler",
                    "credential",
                    "paper_v2",
                    "broker",
                    "robinhood",
                    "unattended",
                    "collector",
                )
            )
            if which in {"observer.py", "native_read.py"}:
                assert node.module not in {
                    "trading_bot.supervised_release.native_write",
                    "trading_bot.supervised_release.installer",
                }
        if isinstance(node, ast.Call):
            assert (
                getattr(node.func, "attr", getattr(node.func, "id", ""))
                not in forbidden_calls
            )
    assert DURABLE_DATA_ROOT not in str(
        ReleasePaths(accepted().manifest.release_id).final
    )


def test_checkpoint_source_only_registration_pins_workflow_and_classifier():
    spec = runner._checkpoint_specs()[NAME]
    assert (
        NAME in runner.ACTIVE_CI_CHECKPOINTS and len(runner.ACTIVE_CI_CHECKPOINTS) == 52
    )
    assert spec.remote_branch == "feature/robinhood-supervised-release-installation"
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner._supervised_release_installation_authority_check(ROOT) == ()
    assert (
        "feature/robinhood-*"
        in (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    )
    inventory = certification.discover_inventory(ROOT)
    for profile in ("full", "robinhood"):
        assert (
            "tests/review_paper/test_supervised_release_installation.py"
            in certification.select_inventory(inventory, profile)
        )


def test_source_pins_and_import_boundary_fail_closed(tmp_path, monkeypatch):
    for path in (
        *runner.SUPERVISED_RELEASE_SOURCES,
        *runner.SUPERVISED_RELEASE_BUNDLE_SOURCES,
        *runner.SUPERVISED_RELEASE_INSTALLATION_SOURCES,
        *runner.SUPERVISED_RELEASE_NATIVE_PRIMITIVE_PINS,
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (ROOT / path).read_text(encoding="utf-8-sig"), encoding="utf-8"
        )
    assert runner._supervised_release_installation_authority_check(tmp_path) == ()
    target = tmp_path / "src/trading_bot/supervised_release/observer.py"
    target.write_text(
        target.read_text()
        + "\nfrom trading_bot.supervised_release.native_write import WindowsInstaller\n"
    )
    assert runner._supervised_release_installation_authority_check(tmp_path)
    pins = dict(runner.SUPERVISED_RELEASE_INSTALLATION_PINS)
    pins["src/trading_bot/supervised_release/observer.py"] = runner._git_blob_sha1(
        target
    )
    monkeypatch.setattr(runner, "SUPERVISED_RELEASE_INSTALLATION_PINS", pins)
    assert (
        "release installation import boundary drift"
        in runner._supervised_release_installation_authority_check(tmp_path)
    )


@pytest.mark.parametrize(
    "phase", ["create", "write", "partial_write", "flush", "close", "success"]
)
def test_native_writes_are_create_new_one_write_flush_close_only(
    environment, monkeypatch, phase
):
    _, _, native = environment
    session = object.__new__(native_write.WindowsWriteSession)
    session.paths, session.kernel = native.paths, object()
    calls = []
    monkeypatch.setattr(session, "pin_creation_parent", lambda path: None)

    class Attributes(ctypes.Structure):
        _fields_ = [("length", ctypes.c_uint32)]

    @contextmanager
    def security():
        yield Attributes(4)

    monkeypatch.setattr(native_write, "image_security_attributes", security)

    def binding(kernel, name, args, result):
        def call(*values):
            calls.append(name)
            if name == "CreateFileW":
                assert values[1:3] == (0x40000000, 0)
                assert values[4:6] == (1, 0x80200080)
                assert values[0].startswith(native.paths.staging + "\\")
                return ctypes.c_void_p(-1).value if phase == "create" else 23
            if name == "WriteFile":
                assert values[0] == 23 and values[2] == 4
                values[3]._obj.value = 3 if phase == "partial_write" else 4
                return 0 if phase == "write" else 1
            if name == "FlushFileBuffers":
                return 0 if phase == "flush" else 1
            pytest.fail("unreviewed native API: " + name)

        return call

    monkeypatch.setattr(native_write, "bind", binding)

    def close(kernel, handle):
        calls.append("CloseHandle")
        assert handle == 23
        if phase == "close":
            raise native_read.NativeObservationError("native close failed")

    monkeypatch.setattr(native_write, "close_native_handle", close)
    path = native.paths.child(native.paths.staging, "pyproject.toml")
    if phase == "success":
        session.write_file(path, b"data")
    else:
        with pytest.raises(native_read.NativeObservationError):
            session.write_file(path, b"data")
    assert calls.count("CreateFileW") == 1
    assert calls.count("WriteFile") <= 1
    assert calls.count("FlushFileBuffers") == (phase in {"flush", "close", "success"})
    assert calls.count("CloseHandle") == (phase != "create")


@pytest.mark.parametrize("operation", ["create_directory", "write_file"])
def test_native_mutation_rejects_final_durable_and_scratch_before_binding(
    environment, monkeypatch, operation
):
    _, _, native = environment
    session = object.__new__(native_write.WindowsWriteSession)
    session.paths = native.paths
    monkeypatch.setattr(
        native_write, "bind", lambda *args: pytest.fail("native called")
    )
    for path in (
        native.paths.final,
        DURABLE_DATA_ROOT,
        PRODUCTION_PYTHON,
        r"F:\AI\temp\arch133z-rename-qualification",
    ):
        with pytest.raises((ValueError, native_read.NativeObservationError)):
            if operation == "write_file":
                session.write_file(path, b"data")
            else:
                session.create_directory(path)


def test_native_python_version_resource_is_read_without_execution(
    environment, monkeypatch
):
    _, _, native = environment
    session = object.__new__(native_read.WindowsReadSession)
    session.paths = native.paths
    session.handles = {PRODUCTION_PYTHON: 11}
    value = ctypes.create_unicode_buffer(PYTHON_VERSION)
    calls = []
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *args, **kwargs: object(), raising=False
    )

    def binding(kernel, name, args, result):
        def call(*values):
            calls.append(name)
            if name == "GetFileVersionInfoSizeW":
                assert values[0] == PRODUCTION_PYTHON
                return 512
            if name == "GetFileVersionInfoW":
                assert values[0] == PRODUCTION_PYTHON
                return 1
            assert name == "VerQueryValueW"
            assert values[1] == r"\StringFileInfo\000004b0\ProductVersion"
            values[2]._obj.value = ctypes.addressof(value)
            values[3]._obj.value = len(value)
            return 1

        return call

    monkeypatch.setattr(native_read, "bind", binding)
    assert session.python_version() == PYTHON_VERSION
    assert calls == ["GetFileVersionInfoSizeW", "GetFileVersionInfoW", "VerQueryValueW"]


@pytest.mark.parametrize("phase", ["staging", "final"])
def test_observation_identity_drift_across_publication_fails_closed(environment, phase):
    release, binding, native = environment

    def hook(backend, scope):
        if scope == (1 if phase == "staging" else 2):
            path = RELEASES_BASE if phase == "staging" else backend.paths.final
            backend.nodes[path] = replace(backend.nodes[path], identity=(7, 10001))

    native.hook = hook
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.INDETERMINATE
    assert result.reason is (
        InstallReason.STAGING_VERIFICATION
        if phase == "staging"
        else InstallReason.FINAL_VERIFICATION
    )


def test_new_namespace_entry_during_observation_is_rejected(environment, monkeypatch):
    release, binding, native = environment
    native.seed(release)
    original = native.names
    reads = 0

    def names(path):
        nonlocal reads
        if path == native.paths.final:
            reads += 1
            if reads == 2:
                return (*original(path), "new-file")
        return original(path)

    monkeypatch.setattr(native, "names", names)
    with pytest.raises(ValueError, match="directory observation drift"):
        observer.observe_installed_release(release, binding, native=native)


@pytest.mark.parametrize(
    "field",
    ["dependency_closure", "durable_data_root", "release_root", "manifest_sha256"],
)
def test_binding_material_replayed_exactly_before_host_observation(
    environment, monkeypatch, field
):
    release, binding, native = environment
    original = RuntimeBinding.to_dict
    monkeypatch.setattr(
        RuntimeBinding,
        "to_dict",
        lambda self: (
            original(self) | {field: "tampered"} if self is binding else original(self)
        ),
    )
    result = installer.install_release(release, binding, native=native)
    assert result.status is InstallStatus.BLOCKED
    assert result.reason is InstallReason.INPUT and native.events == []


def test_native_security_descriptor_is_exact_protected_read_execute_policy(monkeypatch):
    calls = []
    monkeypatch.setattr(native_write, "windows_libraries", lambda: (object(), object()))

    def binding(kernel, name, args, result):
        def call(*values):
            calls.append(name)
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                assert values[0] == "O:" + ADMINISTRATORS_SID + "D:P" + "".join(
                    f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in IMAGE_ACES
                )
                assert values[1] == 1
                values[2]._obj.value = 123
                return 1
            assert name == "LocalFree"
            return None

        return call

    monkeypatch.setattr(native_write, "bind", binding)
    with native_write.image_security_attributes() as attributes:
        assert attributes.descriptor == 123 and attributes.inherit_handle == 0
    assert calls == [
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        "LocalFree",
    ]
