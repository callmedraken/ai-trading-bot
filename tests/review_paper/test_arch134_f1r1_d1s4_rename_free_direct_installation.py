"""D1S4 disposable fake-host verification; no production namespace is accessed."""

import ast
import builtins
import ctypes
import hashlib
import inspect
import json
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import deployment_admission as readonly
from trading_bot.supervised_release import (
    deployment_admission_source as readonly_source,
)
from trading_bot.supervised_release import deployment_candidate as candidate
from trading_bot.supervised_release import successor_direct_installation as d
from trading_bot.supervised_release import successor_native_direct_write as native
from trading_bot.supervised_release import successor_source as fresh
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseBundle,
    ReleaseFile,
    VerifiedRelease,
)
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    ObjectFacts,
    ReleasePaths,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    RELEASES_BASE,
    STRATEGY_ID,
    ReleaseInventoryEntry,
    ReleaseManifest,
    release_root,
)

ROOT = Path(__file__).resolve().parents[2]
FAKE_PYTHON = b"disposable Python binary"


def accepted(head="a" * 40, tree="b" * 40):
    files = {
        "pyproject.toml": b"[project]\nname='fake'\n",
        LAUNCHER_RELATIVE_PATH: b"# inert launcher\n",
        "src/trading_bot/__init__.py": b"",
        "src/trading_bot/runtime/example.py": b"# source\n",
    }
    manifest = ReleaseManifest(
        head,
        tree,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        hashlib.sha256(files[LAUNCHER_RELATIVE_PATH]).hexdigest(),
        tuple(
            ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest())
            for name, data in sorted(files.items())
        ),
        STRATEGY_ID,
        "1.0.0",
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
        "reviewed-policy",
        "1.0.0",
        "d" * 64,
    )
    files["manifest.json"] = manifest.to_json().encode()
    return VerifiedRelease(
        ReleaseBundle(
            tuple(ReleaseFile(name, data) for name, data in sorted(files.items()))
        ),
        hashlib.sha256(files["manifest.json"]).hexdigest(),
        head,
        tree,
        tuple(sorted(name for name in files if name != "manifest.json")),
    )


class FakeHost:
    def __init__(self, release):
        self.release = release
        self.paths = ReleasePaths(release.manifest.release_id)
        self.nodes, self.data, self.events = {}, {}, []
        for path in (*ANCESTORS, r"F:\AITradingBot\runtime"):
            self.add(path, True)
        self.add(PRODUCTION_PYTHON, False, FAKE_PYTHON)

    def add(self, path, directory, data=b""):
        self.nodes[path] = ObjectFacts(
            path,
            "directory" if directory else "file",
            (7, len(self.nodes) + 10),
            ADMINISTRATORS_SID,
            True,
            IMAGE_ACES,
            size=len(data),
        )
        self.data[path] = data

    @contextmanager
    def read_session(self, paths):
        assert paths == self.paths
        self.events.append("read_open")
        yield self
        self.events.append("read_close")

    def object(self, path, *, directory):
        assert ".installing" not in path
        return self.nodes.get(path)

    def names(self, path):
        prefix = path + "\\"
        return tuple(
            name[len(prefix) :]
            for name in self.nodes
            if name.startswith(prefix) and "\\" not in name[len(prefix) :]
        )

    def read(self, path, limit):
        assert len(self.data[path]) <= limit
        return self.data[path]

    def python_version(self):
        return PYTHON_VERSION

    def seed(self):
        self.add(self.paths.final, True)
        for item in self.release.bundle.files:
            for parent in reversed(PureWindowsPath(item.relative_path).parents):
                if str(parent) != ".":
                    child = self.paths.child(
                        self.paths.final, str(parent).replace("\\", "/")
                    )
                    if child not in self.nodes:
                        self.add(child, True)
            self.add(
                self.paths.child(self.paths.final, item.relative_path), False, item.data
            )


@pytest.fixture
def host(monkeypatch, tmp_path):
    release = accepted()
    state = FakeHost(release)
    monkeypatch.setattr(d, "ATTEMPT_ROOT", tmp_path)
    monkeypatch.setattr(
        d,
        "admit_source",
        lambda: (release.expected_source_head, release.expected_source_tree),
    )
    monkeypatch.setattr(
        d, "reconstruct_release", lambda: (release, RuntimeBinding(release))
    )
    monkeypatch.setattr(
        d, "require_administrator", lambda: state.events.append("administrator")
    )
    monkeypatch.setattr(d, "WindowsObserver", lambda: state)
    from trading_bot.supervised_release import observer

    fake_hashes = SimpleNamespace(
        sha256=lambda data: (
            SimpleNamespace(hexdigest=lambda: PYTHON_SHA256)
            if data == FAKE_PYTHON
            else hashlib.sha256(data)
        )
    )
    monkeypatch.setattr(observer, "hashlib", fake_hashes)
    monkeypatch.setattr(d, "hashlib", fake_hashes)
    original = d.observe_installed_release

    def observe(release, binding):
        state.events.append("final_replay")
        return original(release, binding, native=state)

    monkeypatch.setattr(d, "observe_installed_release", observe)
    monkeypatch.delenv(d.AUTH_ENV, raising=False)
    return state


def authorize(monkeypatch, host, outcome=True):
    monkeypatch.setenv(d.AUTH_ENV, d.AUTH_VALUE)

    def materialize(release, binding, parent, python):
        assert d.observe_attempt(release).classification == "CONSUMED"
        assert d.attempt_path(release).read_bytes() == d.attempt_bytes(release)
        host.events.append("create_final")
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is True:
            host.seed()
        host.events.append("materialization_close")
        return outcome

    monkeypatch.setattr(native, "materialize_release", materialize)


def test_release_path_and_latch_are_exact_and_deterministic():
    first = accepted()
    second = accepted("c" * 40, "e" * 40)
    assert first == accepted()
    identifier = first.manifest.release_id
    assert release_root(identifier) == RELEASES_BASE + "\\" + identifier
    assert identifier != second.manifest.release_id
    assert (
        d.attempt_path(first).name
        == "arch134-f1r1-d1s4-direct-install-attempt-" + identifier + ".json"
    )
    assert str(d.attempt_path(first).parent) == r"F:\AI\temp"
    assert d.ATTEMPT_SCHEMA == "arch134-f1r1-d1s4-rename-free-direct-install-attempt/v1"
    assert json.loads(d.attempt_bytes(first)) == {
        "schema": d.ATTEMPT_SCHEMA,
        "release_id": identifier,
        "source_head": "a" * 40,
        "source_tree": "b" * 40,
        "status": "CONSUMED",
        "automatic_retry": "NOT_AUTHORIZED",
    }
    assert identifier != d.INCIDENT_RELEASE_ID
    assert not inspect.signature(d.attempt_path).parameters.keys() - {"release"}
    assert not inspect.signature(d.consume_attempt).parameters.keys() - {"release"}


@pytest.mark.parametrize(
    "consumed,present,exact,status,reason,eligible",
    [
        (False, False, False, "PASS", "READY_FOR_RENAME_FREE_MATERIALIZATION", True),
        (True, True, True, "PASS", "DIRECT_INSTALL_VERIFIED", False),
        (True, False, False, "BLOCKED", "CONSUMED_ATTEMPT_NO_IMAGE", False),
        (True, True, False, "BLOCKED", "PARTIAL_OR_CONFLICTING_DEPLOYMENT", False),
        (False, True, True, "BLOCKED", "UNOWNED_FINAL_PRESENT", False),
        (False, True, False, "BLOCKED", "UNOWNED_FINAL_PRESENT", False),
    ],
)
def test_reconciliation_table(host, consumed, present, exact, status, reason, eligible):
    if consumed:
        d.consume_attempt(host.release)
    if present:
        host.seed() if exact else host.add(host.paths.final, True)
    result = d.preflight()
    assert result["status"] == status
    assert result["primary"]["reason"] == reason
    assert result["primary"]["execute_eligible"] is eligible
    assert result["effect_disposition"] == "NOT_STARTED"
    assert result["automatic_retry"] == "NOT_AUTHORIZED"
    assert all(count == 0 for _, count in result["protected_effects"])
    assert "create_final" not in host.events
    primary = result["primary"]
    assert primary["source_head"] == "a" * 40 and primary["source_tree"] == "b" * 40
    assert primary["final_path"] == host.paths.final
    assert primary["manifest_sha256"] == host.release.expected_manifest_sha256
    assert primary["binding_sha256"] == RuntimeBinding(host.release).sha256
    assert primary["parent_identity"] == host.nodes[RELEASES_BASE].identity
    assert primary["python_identity"] == host.nodes[PRODUCTION_PYTHON].identity
    assert primary["repeated_observation_stable"] is True


@pytest.mark.parametrize("payload", [b"", b"{}", b"CONSUMED", b"x" * 4097])
def test_unprovable_latch_never_authorizes(host, payload):
    d.attempt_path(host.release).write_bytes(payload)
    result = d.preflight()
    assert result["status"] == "INDETERMINATE"
    assert result["primary"]["execute_eligible"] is False


@pytest.mark.parametrize(
    "changed", ["parent", "python", "names", "final", "latch", "source"]
)
def test_observation_drift(host, monkeypatch, changed):
    original = d.observe_namespace
    calls = []

    def observe(*args):
        value = original(*args)
        calls.append(value)
        if len(calls) > 1:
            if changed in {"parent", "python"}:
                return replace(
                    value,
                    **{changed: replace(getattr(value, changed), identity=(7, 999))},
                )
            if changed == "names":
                return replace(value, names=("unrelated",))
            if changed == "final":
                return replace(
                    value, final=replace(value.parent, path=host.paths.final)
                )
        return value

    monkeypatch.setattr(d, "observe_namespace", observe)
    if changed == "latch":
        original_attempt = d.observe_attempt
        n = []

        def attempt(release):
            n.append(1)
            value = original_attempt(release)
            return replace(value, classification="CONSUMED") if len(n) > 1 else value

        monkeypatch.setattr(d, "observe_attempt", attempt)
    if changed == "source":
        n = []

        def source():
            n.append(1)
            return ("a" * 40, "b" * 40) if len(n) == 1 else ("c" * 40, "b" * 40)

        monkeypatch.setattr(d, "admit_source", source)
    result = d.preflight()
    assert result["status"] == "INDETERMINATE"
    assert result["primary"]["execute_eligible"] is False


@pytest.mark.parametrize(
    "path,changes",
    [
        (RELEASES_BASE, {"aces": ()}),
        (RELEASES_BASE, {"protected": False}),
        (RELEASES_BASE, {"reparse": True}),
        (RELEASES_BASE, {"owner": "foreign"}),
        (PRODUCTION_PYTHON, {"owner": "foreign"}),
        (PRODUCTION_PYTHON, {"links": 2}),
        (PRODUCTION_PYTHON, {"size": 1}),
    ],
)
def test_parent_and_python_policy(host, path, changes):
    host.nodes[path] = replace(host.nodes[path], **changes)
    assert d.preflight()["status"] == "BLOCKED"


def test_python_hash_and_resource_version(host, monkeypatch):
    host.data[PRODUCTION_PYTHON] = b"wrong"
    assert d.preflight()["status"] == "BLOCKED"
    host.data[PRODUCTION_PYTHON] = FAKE_PYTHON
    monkeypatch.setattr(host, "python_version", lambda: "0.0.0")
    assert d.preflight()["status"] == "BLOCKED"


def test_success_latch_import_create_close_and_two_replays(host, monkeypatch):
    authorize(monkeypatch, host)
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.endswith("successor_native_direct_write"):
            assert d.attempt_path(host.release).read_bytes() == d.attempt_bytes(
                host.release
            )
            host.events.append("native_import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = d.execute_once()
    assert result["status"] == "PASS" and result["effect_disposition"] == "CONFIRMED"
    assert result["primary"]["reason"] == "DIRECT_INSTALL_VERIFIED"
    assert host.events.index("native_import") < host.events.index("create_final")
    assert host.events.index("materialization_close") < host.events.index(
        "final_replay"
    )
    assert host.events.count("final_replay") == 2
    assert d.execute_once()["status"] == "BLOCKED"
    assert host.events.count("create_final") == 1
    assert d.preflight()["primary"]["reason"] == "DIRECT_INSTALL_VERIFIED"
    assert d.preflight()["primary"]["execute_eligible"] is False


@pytest.mark.parametrize(
    "outcome", [False, None, OSError(), ValueError(), KeyboardInterrupt(), SystemExit()]
)
def test_native_ambiguity_is_terminal(host, monkeypatch, outcome):
    authorize(monkeypatch, host, outcome)
    result = d.execute_once()
    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["primary"]["disposition"] == d.PRESERVE
    assert d.observe_attempt(host.release).classification == "CONSUMED"
    assert d.execute_once()["status"] == "BLOCKED"
    assert host.events.count("create_final") == 1
    assert d.preflight()["primary"]["reason"] == "CONSUMED_ATTEMPT_NO_IMAGE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_identity", (7, 999)),
        ("parent_identity", (7, 999)),
        ("python_identity", (7, 999)),
        ("manifest_sha256", "c" * 64),
        ("binding_sha256", "c" * 64),
        ("python_sha256", "c" * 64),
        ("python_version", "3.12.0"),
        ("release_id", "foreign"),
    ],
)
def test_post_create_replay_agreement(host, monkeypatch, field, value):
    authorize(monkeypatch, host)
    original = d.observe_installed_release
    monkeypatch.setattr(
        d,
        "observe_installed_release",
        lambda *args: replace(original(*args), **{field: value}),
    )
    assert d.execute_once()["status"] == "INDETERMINATE"
    assert d.preflight()["primary"]["reason"] == "PARTIAL_OR_CONFLICTING_DEPLOYMENT"


def test_independent_replays_must_have_identical_identity(host, monkeypatch):
    authorize(monkeypatch, host)
    original = d.verify_final
    n = []

    def replay(*args):
        n.append(1)
        value = original(*args)
        return replace(value, image_identity=(7, 999)) if len(n) > 1 else value

    monkeypatch.setattr(d, "verify_final", replay)
    assert d.execute_once()["status"] == "INDETERMINATE"


@pytest.mark.parametrize(
    "seam", ["admit_source", "observe_namespace", "observe_attempt", "verify_final"]
)
def test_post_fence_drift(host, monkeypatch, seam):
    authorize(monkeypatch, host)
    original = getattr(d, seam)

    def changed(*args, **kwargs):
        if "create_final" in host.events:
            raise d.ObservationDrift("injected")
        return original(*args, **kwargs)

    monkeypatch.setattr(d, seam, changed)
    result = d.execute_once()
    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"


@pytest.mark.parametrize("phase", ["write", "flush", "fsync", "close", "readback"])
def test_latch_failures_before_native_import(host, monkeypatch, phase):
    authorize(monkeypatch, host)
    original = Path.open
    path = d.attempt_path(host.release)

    class Broken:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()
            if phase == "close":
                raise OSError("close")

        def write(self, data):
            return self.handle.write(data[:1] if phase == "write" else data)

        def flush(self):
            if phase == "flush":
                raise OSError("flush")
            self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    monkeypatch.setattr(
        Path,
        "open",
        lambda self, mode="r", *a, **k: (
            Broken(original(self, mode, *a, **k))
            if self == path and mode == "xb"
            else original(self, mode, *a, **k)
        ),
    )
    if phase == "fsync":
        monkeypatch.setattr(d.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError()))
    elif phase == "readback":
        monkeypatch.setattr(d, "read_record", lambda *args: (b"wrong", (7, 1)))
    result = d.execute_once()
    assert result["status"] == "INDETERMINATE"
    assert result["automatic_retry"] == "NOT_AUTHORIZED"
    assert "create_final" not in host.events
    assert path.exists()


def test_latch_exclusive_no_overwrite_and_no_old_authority(host):
    first = d.consume_attempt(host.release)
    payload = d.attempt_path(host.release).read_bytes()
    assert first.classification == "CONSUMED"
    with pytest.raises(ValueError):
        d.consume_attempt(host.release)
    assert d.attempt_path(host.release).read_bytes() == payload
    assert "d1s3" not in first.path and "r5" not in first.path


def test_incident_sibling_is_only_an_unrelated_name(host):
    host.nodes[d.INCIDENT_RELEASE_ID + ".installing"] = object()
    # A sibling is enumerated but never opened or read as D1S4 input.
    host.nodes[RELEASES_BASE + "\\" + d.INCIDENT_RELEASE_ID + ".installing"] = object()
    result = d.preflight()
    assert result["primary"]["execute_eligible"] is True


def test_execute_requires_only_exact_d1s4_authority(host, monkeypatch):
    assert d.execute_once()["primary"]["reason"] == "AUTHORIZATION_REJECTED"
    for name, value in (
        (
            "AI_TRADING_BOT_ARCH134_F1R1_D1S3_INSTALL_AUTHORIZATION",
            "ARCH134_F1R1_D1S3_SUCCESSOR_INSTALLATION_AUTHORIZED",
        ),
        (
            "AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_PUBLICATION_AUTHORIZATION",
            "ARCH134_F1R1_D1S3_R5_ONE_PRESERVED_RELEASE_PUBLICATION_AUTHORIZED",
        ),
    ):
        monkeypatch.setenv(name, value)
    assert d.execute_once()["primary"]["reason"] == "AUTHORIZATION_REJECTED"
    assert not d.attempt_path(host.release).exists()


@pytest.mark.parametrize(
    "bad",
    [
        "head",
        "tree",
        "branch",
        "origin",
        "status",
        "index",
        "base",
        "remote",
        "flags",
        "root",
        "interlock",
    ],
)
def test_exact_source_admission_rejects_each_mismatch(monkeypatch, bad):
    monkeypatch.setenv(d.REMOTE_HEAD_ENV, "a" * 40)
    monkeypatch.setenv(d.SOURCE_TREE_ENV, "b" * 40)
    mapping = {
        ("rev-parse", "HEAD"): b"a" * 40,
        ("rev-parse", "HEAD^{tree}"): b"b" * 40,
        ("branch", "--show-current"): d.BRANCH.encode(),
        ("remote", "get-url", "origin"): d.ORIGIN.encode(),
        ("status", "--porcelain=v1", "--untracked-files=all"): b"",
        ("diff", "--cached", "--name-only"): b"",
        ("merge-base", d.BASE_HEAD, "HEAD"): d.BASE_HEAD.encode(),
        ("rev-parse", d.BASE_HEAD + "^{tree}"): d.BASE_TREE.encode(),
        ("rev-parse", "--show-toplevel"): str(ROOT).encode(),
        ("ls-files", "-v", "-z"): b"H source.py\0",
        ("ls-remote", "origin", "refs/heads/" + d.BRANCH): (
            "a" * 40 + "\trefs/heads/" + d.BRANCH
        ).encode(),
    }
    monkeypatch.setattr(d, "WORKTREE", ROOT)
    assert d.admit_source.__module__ == d.__name__
    keys = list(mapping)
    chosen = {
        "head": 0,
        "tree": 1,
        "branch": 2,
        "origin": 3,
        "status": 4,
        "index": 5,
        "base": 6,
        "root": 8,
        "flags": 9,
        "remote": 10,
    }
    monkeypatch.setattr(d, "_git", lambda *args: mapping[args])
    assert d.admit_source() == ("a" * 40, "b" * 40)
    if bad == "interlock":
        monkeypatch.setenv(d.REMOTE_HEAD_ENV, "wrong")
    else:
        mapping[keys[chosen[bad]]] = b"wrong"
    with pytest.raises(ValueError):
        d.admit_source()


def test_native_derived_tree_and_no_arbitrary_destinations(monkeypatch):
    release = accepted()
    monkeypatch.setattr(
        native.WindowsReadSession,
        "__init__",
        lambda self, paths: setattr(self, "paths", paths),
    )
    session = native._DirectSession(release, RuntimeBinding(release))
    events = []
    monkeypatch.setattr(
        session, "_create_directory", lambda name: events.append(("directory", name))
    )
    monkeypatch.setattr(
        session,
        "_write_inventory_file",
        lambda ordinal: events.append(("file", ordinal)),
    )
    session.materialize()
    assert events[0] == ("directory", None)
    assert ("directory", "src/trading_bot/runtime") in events
    assert [n for kind, n in events if kind == "file"] == list(
        range(len(release.bundle.files))
    )
    assert not set(inspect.signature(native.materialize_release).parameters) & {
        "path",
        "destination",
        "root",
    }


@pytest.mark.parametrize(
    "phase", ["ok", "create", "write", "partial", "flush", "close"]
)
def test_native_create_new_bounded_write_flush_close(monkeypatch, phase):
    release = accepted()
    session = object.__new__(native._DirectSession)
    session.release, session.paths, session.created = (
        release,
        ReleasePaths(release.manifest.release_id),
        True,
    )
    session.kernel = object()
    events = []
    monkeypatch.setattr(session, "_pin_parent", lambda path: None)

    @contextmanager
    def attributes():
        yield ctypes.c_uint32(1)

    monkeypatch.setattr(native, "image_security_attributes", attributes)

    def bind(kernel, name, args, result):
        def call(*values):
            events.append(name)
            if name == "CreateFileW":
                path, access, share, security, disposition, flags, template = values
                assert path.startswith(session.paths.final + "\\")
                assert (access, share, disposition, flags, template) == (
                    0x40000000,
                    0,
                    1,
                    0x80200080,
                    None,
                )
                assert ".installing" not in path
                return None if phase == "create" else 42
            if name == "WriteFile":
                ctypes.cast(
                    values[3], ctypes.POINTER(ctypes.c_uint32)
                ).contents.value = values[2] - (phase == "partial")
                return phase != "write"
            assert name == "FlushFileBuffers"
            return phase != "flush"

        return call

    monkeypatch.setattr(native, "bind", bind)

    def close(kernel, handle):
        assert handle == 42
        events.append("close")
        if phase == "close":
            raise native.NativeObservationError("ambiguous")

    monkeypatch.setattr(native, "close_native_handle", close)
    if phase == "ok":
        session._write_inventory_file(0)
        assert events == ["CreateFileW", "WriteFile", "FlushFileBuffers", "close"]
    else:
        with pytest.raises(native.NativeObservationError):
            session._write_inventory_file(0)
        assert events[-1] == ("CreateFileW" if phase == "create" else "close")


def test_native_security_exact_sddl(monkeypatch):
    calls = []
    monkeypatch.setattr(native, "windows_libraries", lambda: (object(), object()))

    def bind(library, name, args, result):
        def call(*values):
            calls.append(name)
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                assert values[0] == "O:" + IMAGE_ACES[0][0] + "D:P" + "".join(
                    f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in IMAGE_ACES
                )
                ctypes.cast(
                    values[2], ctypes.POINTER(ctypes.c_void_p)
                ).contents.value = 123
                return 1
            assert name == "LocalFree"

        return call

    monkeypatch.setattr(native, "bind", bind)
    with native.image_security_attributes() as attributes:
        assert attributes.descriptor == 123 and not attributes.inherit_handle
    assert calls == [
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        "LocalFree",
    ]


def test_native_close_ambiguity_closes_every_remaining_handle(monkeypatch):
    session = object.__new__(native._DirectSession)
    session.kernel, session.handles = object(), {"first": 1, "second": 2}
    calls = []

    def close(kernel, handle):
        calls.append(handle)
        if handle == 2:
            raise SystemExit()

    monkeypatch.setattr(native, "close_native_handle", close)
    with pytest.raises(native.NativeObservationError):
        session.close()
    assert calls == [2, 1] and session.handles == {}


def test_registered_forward_dispatch_and_authority(monkeypatch):
    spec = runner._checkpoint_specs()[d.CHECKPOINT]
    assert spec.preflight is runner._arch134_d1s4_preflight
    assert spec.execute is runner._arch134_d1s4_execute
    assert spec.remote_branch == d.BRANCH and spec.remote_head_env == d.REMOTE_HEAD_ENV
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), d.BRANCH, "push")
        == d.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[d.CHECKPOINT] == "robinhood"
    assert runner._arch134_d1s4_graph_check(ROOT) == ()
    assert runner._arch134_d1s4_authority_check(ROOT) == ()
    for function in (spec.preflight, spec.execute):
        tree = ast.parse(inspect.getsource(function))
        imports = [
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert imports == [
            "trading_bot.supervised_release.successor_direct_installation"
        ]


@pytest.mark.parametrize(
    "injection",
    [
        "from trading_bot.supervised_release import installer",
        "from trading_bot.supervised_release import native_write",
        "from trading_bot.supervised_release import successor_installation_operator",
        "from trading_bot.supervised_release import successor_publication_recovery",
        "from trading_bot.supervised_release import successor_native_publication",
        "from trading_bot.arch133_windows_rename_qualification import native",
        "from trading_bot.arch133_closed_descendant_rename_qualification "
        "import operator",
        "from scripts import d10_protected_replacement_windows",
        "from trading_bot import review_paper",
        "from trading_bot import brokers",
        "import os; os.rename('a', 'b')",
        "import os; os.replace('a', 'b')",
        "from pathlib import Path; Path('a').rename('b')",
        "from pathlib import Path; Path('a').replace('b')",
        "def publish(): pass",
        "def delete(): pass",
        "def cleanup(): pass",
        "def promote(): pass",
        "def rollback(): pass",
        "primitive = 'SetFileInformationByHandle'",
        "primitive = 'MoveFileExW'",
        "__import__('retired')",
        "import trading_bot.supervised_release as releases; "
        "releases.installer.install_release(None, None)",
        "import trading_bot.supervised_release as releases; "
        "releases.successor_publication_recovery.execute_once()",
    ],
)
def test_machine_graph_rejects_retired_and_namespace_shortcuts(monkeypatch, injection):
    original = Path.read_text
    target = (
        ROOT / "src/trading_bot/supervised_release/successor_native_direct_write.py"
    )

    def read(path, *args, **kwargs):
        source = original(path, *args, **kwargs)
        return source + "\n" + injection + "\n" if path == target else source

    monkeypatch.setattr(Path, "read_text", read)
    failures = runner._arch134_d1s4_graph_check(ROOT)
    assert failures, injection


def test_graph_baseline_has_no_retired_or_unrelated_effect_reachability():
    assert runner._arch134_d1s4_graph_check(ROOT) == ()
    forbidden = {
        "publish",
        "rename",
        "move",
        "promote",
        "replace",
        "delete",
        "cleanup",
        "rollback",
        "repair",
    }
    assert not forbidden & set(dir(native))
    assert not forbidden & set(dir(native._DirectSession))


@pytest.mark.parametrize("failure", [False, True])
def test_native_root_create_is_exact_and_first_attempt_is_consumed(
    monkeypatch, failure
):
    session = object.__new__(native._DirectSession)
    session.paths = ReleasePaths(accepted().manifest.release_id)
    session.created, session.directories, session.kernel = False, ("src",), object()
    calls = []
    monkeypatch.setattr(
        session, "_pin_parent", lambda path: calls.append(("pin", path))
    )
    monkeypatch.setattr(
        session,
        "object",
        lambda path, **kw: ObjectFacts(
            path, "directory", (7, 99), ADMINISTRATORS_SID, True, IMAGE_ACES
        ),
    )

    @contextmanager
    def attributes():
        yield ctypes.c_uint32(1)

    monkeypatch.setattr(native, "image_security_attributes", attributes)

    def bind(kernel, name, args, result):
        assert name == "CreateDirectoryW"

        def create(path, security):
            assert session.created is True
            calls.append(("create", path))
            return not failure

        return create

    monkeypatch.setattr(native, "bind", bind)
    if failure:
        with pytest.raises(native.NativeObservationError):
            session._create_directory(None)
    else:
        session._create_directory(None)
        session._create_directory("src")
    assert calls[0] == ("pin", session.paths.final)
    assert calls[1] == ("create", session.paths.final)
    with pytest.raises(native.NativeObservationError):
        session._create_directory(None)
    with pytest.raises(native.NativeObservationError):
        session._create_directory("../../foreign")


@pytest.mark.parametrize(
    "failure", [None, OSError(), KeyboardInterrupt(), SystemExit()]
)
def test_native_entry_closes_before_acknowledgement(host, monkeypatch, failure):
    events = []
    before = d.observe_namespace(host.release, RuntimeBinding(host.release))

    class Session:
        paths = host.paths

        def object(self, path, **kwargs):
            return None

        def materialize(self):
            events.append("materialize")
            if failure is not None:
                raise failure

        def close(self):
            events.append("close")

    monkeypatch.setattr(native, "windows_libraries", lambda: None)
    monkeypatch.setattr(native, "administrator_sid", lambda: "admin")
    monkeypatch.setattr(native, "_DirectSession", lambda *args: Session())
    monkeypatch.setattr(native, "observe_parent", lambda session: before.parent)
    monkeypatch.setattr(d, "observe_python", lambda *args: before.python)
    if failure is None:
        assert (
            native.materialize_release(
                host.release, RuntimeBinding(host.release), before.parent, before.python
            )
            is True
        )
    else:
        with pytest.raises(type(failure)):
            native.materialize_release(
                host.release, RuntimeBinding(host.release), before.parent, before.python
            )
    assert events == ["materialize", "close"]


def test_latch_create_race_cannot_overwrite(host, monkeypatch):
    path = d.attempt_path(host.release)
    path.write_bytes(b"unowned")
    monkeypatch.setattr(
        d, "observe_attempt", lambda release: d.Attempt("AVAILABLE", str(path))
    )
    with pytest.raises(FileExistsError):
        d.consume_attempt(host.release)
    assert path.read_bytes() == b"unowned"


def test_latch_readback_identity_must_match_created_handle(host, monkeypatch):
    original = d.observe_attempt

    def observe(release):
        value = original(release)
        return (
            replace(value, identity=(7, 999))
            if value.classification == "CONSUMED"
            else value
        )

    monkeypatch.setattr(d, "observe_attempt", observe)
    with pytest.raises(ValueError, match="ATTEMPT_READBACK_REJECTED"):
        d.consume_attempt(host.release)


def test_runner_preflight_report_remains_read_only(host, monkeypatch, tmp_path):
    spec = runner._checkpoint_specs()[d.CHECKPOINT]
    source = {"head": "a" * 40, "tree": "b" * 40, "branch": d.BRANCH, "porcelain": ""}
    monkeypatch.setattr(runner, "_git_state", lambda root: source)
    monkeypatch.setenv(d.REMOTE_HEAD_ENV, "a" * 40)
    passed, report_path = runner.preflight_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path / "reports"
    )
    assert passed
    report = json.loads(report_path.read_text())
    assert report["kind"] == "read_only_preflight"
    assert report["production_effects"] == "NOT_RUN"
    assert report["protected_execution"] == "NOT_AUTHORIZED"
    assert "create_final" not in host.events


def test_runner_execute_rejects_wrong_interlock_and_dispatch(
    host, monkeypatch, tmp_path
):
    spec = runner._checkpoint_specs()[d.CHECKPOINT]
    source = {"head": "a" * 40, "tree": "b" * 40, "branch": d.BRANCH, "porcelain": ""}
    monkeypatch.setattr(runner, "_git_state", lambda root: source)
    with pytest.raises(RuntimeError, match="D1S4 authorization"):
        runner.execute_checkpoint(
            spec, repo_root=ROOT, evidence_root=tmp_path / "reports"
        )
    wrong = replace(spec, execute=runner._arch134_r5_execute)
    with pytest.raises(RuntimeError, match="D1S4 registration"):
        runner.execute_checkpoint(
            wrong, repo_root=ROOT, evidence_root=tmp_path / "reports"
        )
    wrong = replace(spec, execute=runner._arch134_d1s3_execute)
    with pytest.raises(RuntimeError, match="D1S4 registration"):
        runner.execute_checkpoint(
            wrong, repo_root=ROOT, evidence_root=tmp_path / "reports"
        )
    assert not (tmp_path / "reports").exists()


def test_runner_post_effect_drift_preserves_direct_diagnostics(
    host, monkeypatch, tmp_path
):
    authorize(monkeypatch, host)
    spec = runner._checkpoint_specs()[d.CHECKPOINT]
    states = iter(
        [
            {"head": "a" * 40, "tree": "b" * 40, "branch": d.BRANCH, "porcelain": ""},
            {"head": "c" * 40, "tree": "b" * 40, "branch": d.BRANCH, "porcelain": ""},
        ]
    )
    monkeypatch.setattr(runner, "_git_state", lambda root: next(states))
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: "a" * 40)
    passed, report_path = runner.execute_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path / "reports"
    )
    assert not passed
    result = json.loads(report_path.read_text())["result"]
    assert result["status"] == "INDETERMINATE"
    assert result["primary"]["disposition"] == d.PRESERVE
    assert result["primary"]["release_id"] == host.release.manifest.release_id
    assert result["primary"]["execute_eligible"] is False
    assert all(count == 0 for _, count in result["protected_effects"])


@pytest.mark.parametrize("drift", [False, True])
def test_reconstructs_complete_exact_source_release(monkeypatch, tmp_path, drift):
    seed = accepted()
    for item in seed.bundle.files:
        if item.relative_path != "manifest.json":
            path = tmp_path / item.relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item.data)
    monkeypatch.setattr(d, "WORKTREE", tmp_path)
    observations = []

    def admit():
        observations.append(1)
        return (
            ("a" * 40, "b" * 40)
            if not drift or len(observations) == 1
            else ("c" * 40, "b" * 40)
        )

    monkeypatch.setattr(d, "admit_source", admit)
    rows = b"\0".join(
        b"100644 blob " + b"1" * 40 + b"\t" + name.encode()
        for name in seed.expected_source_paths
    )
    monkeypatch.setattr(d, "_git", lambda *args: rows)

    def collect(root, *, declaration):
        assert root == tmp_path
        assert (
            tuple(row.relative_path for row in declaration.source_inventory)
            == seed.expected_source_paths
        )
        assert (
            declaration.source_head == "a" * 40 and declaration.source_tree == "b" * 40
        )
        files = [
            item for item in seed.bundle.files if item.relative_path != "manifest.json"
        ]
        manifest = ReleaseFile("manifest.json", declaration.to_json().encode())
        return VerifiedRelease(
            ReleaseBundle(
                tuple(sorted((*files, manifest), key=lambda row: row.relative_path))
            ),
            manifest.sha256,
            "a" * 40,
            "b" * 40,
            seed.expected_source_paths,
        )

    monkeypatch.setattr(d, "collect_release_bundle", collect)
    if drift:
        with pytest.raises(d.ObservationDrift):
            d.reconstruct_release()
    else:
        release, binding = d.reconstruct_release()
        assert binding.verified_release == release
        assert binding.to_dict()["release_root"] == release_root(
            release.manifest.release_id
        )


@pytest.mark.parametrize(
    "phase", ["admit_source", "require_administrator", "observe_namespace"]
)
def test_pre_fence_failure_has_no_native_effect_or_latch(host, monkeypatch, phase):
    authorize(monkeypatch, host)

    def fail(*args):
        raise ValueError("injected")

    monkeypatch.setattr(d, phase, fail)
    result = d.execute_once()
    assert (
        result["status"] == "BLOCKED" and result["effect_disposition"] == "NOT_STARTED"
    )
    assert "create_final" not in host.events
    assert not d.attempt_path(host.release).exists()


@pytest.mark.parametrize(
    "mapping",
    [
        "ARCH134_D1S4_BLOB_PREDECESSORS",
        "ARCH134_D1S4_BLOB_PINS",
        "ARCH134_D1S4_AST_PREDECESSORS",
        "ARCH134_D1S4_AST_PINS",
        "ARCH134_D1S4_NEW_AST_PINS",
        "ARCH134_D1S4_SOURCE_PINS",
    ],
)
def test_direct_authority_maps_fail_closed_on_drift(monkeypatch, mapping):
    monkeypatch.setattr(runner, mapping, {})
    assert runner._arch134_d1s4_authority_check(ROOT)


def test_predecessor_c1_inventory_uses_current_d1s4_overlay(monkeypatch):
    assert (
        runner._arch146a_predecessor_active_digest()
        == runner.ARCH134_FRESH_ACTIVE_SHA256
    )
    assert (
        runner.ARCH134_R5_ACTIVE_CI_CHECKPOINTS_SHA256
        != runner.ARCH134_D1S4_ACTIVE_SHA256
    )
    runner._arch134_f1r1_c1_active_inventory()
    assert runner._arch134_f1r1_c1_authority_check(ROOT) == ()


def test_direct_authority_checks_predecessor_c1_inventory(monkeypatch):
    def reject():
        raise ValueError("injected predecessor C1 inventory drift")

    monkeypatch.setattr(runner, "_arch134_f1r1_c1_active_inventory", reject)
    assert "D1S4 authority unavailable" in runner._arch134_d1s4_authority_check(ROOT)


@pytest.mark.parametrize(
    "stage",
    [
        "SOURCE_ADMISSION",
        "RELEASE_RECONSTRUCTION",
        "ADMINISTRATOR_ADMISSION",
        "PARENT_OBSERVATION",
        "PRODUCTION_PYTHON_OBSERVATION",
        "NAMESPACE_ENUMERATION",
        "FINAL_OBJECT_OBSERVATION",
        "ATTEMPT_OBSERVATION",
        "FINAL_IMAGE_REPLAY",
        "REPEAT_ADMISSION",
    ],
)
def test_read_only_failure_stage_is_closed_and_sanitized(host, monkeypatch, stage):
    def reject(*args, **kwargs):
        raise OSError("SECRET arbitrary native error and user-selected path")

    targets = {
        "SOURCE_ADMISSION": "admit_source",
        "RELEASE_RECONSTRUCTION": "reconstruct_release",
        "ADMINISTRATOR_ADMISSION": "require_administrator",
        "PARENT_OBSERVATION": "observe_parent",
        "PRODUCTION_PYTHON_OBSERVATION": "observe_python",
        "ATTEMPT_OBSERVATION": "observe_attempt",
    }
    if stage in targets:
        monkeypatch.setattr(d, targets[stage], reject)
    elif stage == "NAMESPACE_ENUMERATION":
        monkeypatch.setattr(host, "names", reject)
    elif stage == "FINAL_OBJECT_OBSERVATION":
        original = host.object

        def observe(path, *, directory):
            if path == host.paths.final:
                reject()
            return original(path, directory=directory)

        monkeypatch.setattr(host, "object", observe)
    elif stage == "FINAL_IMAGE_REPLAY":
        d.consume_attempt(host.release)
        host.seed()
        monkeypatch.setattr(d, "verify_final", reject)
    else:
        original = d.observe_namespace
        calls = 0

        def repeat(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                reject()
            return original(*args)

        monkeypatch.setattr(d, "observe_namespace", repeat)
    result = d.preflight()
    assert result["status"] == "BLOCKED"
    assert result["primary"]["admission_stage"] == stage
    assert result["primary"]["admission_code"] == "ADMISSION_REJECTED"
    assert "SECRET" not in json.dumps(result)
    assert "arbitrary" not in json.dumps(result)


def test_actual_shared_ancestor_john_full_control_incident_fails_closed(host):
    from trading_bot import shared_namespace_acl_recovery as recovery

    runtime_before = host.nodes[r"F:\AITradingBot\runtime"]
    python_before = host.nodes[PRODUCTION_PYTHON]
    for index, path in enumerate(recovery.TARGET_PATHS):
        row = host.nodes[path]
        host.nodes[path] = replace(row, aces=recovery.PRE_ACES[index])
    result = d.preflight()
    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "READ_ONLY_ADMISSION_REJECTED"
    assert result["primary"]["admission_stage"] == "PARENT_OBSERVATION"
    assert result["primary"]["execute_eligible"] is False
    assert host.nodes[r"F:\AITradingBot\runtime"] == runtime_before
    assert host.nodes[PRODUCTION_PYTHON] == python_before


def test_real_malformed_latch_has_sanitized_attempt_localization(host):
    d.attempt_path(host.release).write_bytes(b"malformed")
    row = d.preflight()["primary"]
    assert row["status"] == "INDETERMINATE"
    assert row["admission_stage"] == "ATTEMPT_OBSERVATION"
    assert row["admission_code"] == "LATCH_UNPROVEN"


# Post-R1 fresh successor source: no native host or installation dispatch.


@pytest.mark.parametrize(
    "bad",
    [
        "head",
        "tree",
        "branch",
        "origin",
        "status",
        "index",
        "base",
        "remote",
        "flags",
        "root",
        "interlock",
    ],
)
def test_fresh_exact_source_admission_rejects_each_mismatch(monkeypatch, bad):
    monkeypatch.setenv(fresh.REMOTE_HEAD_ENV, "a" * 40)
    monkeypatch.setenv(fresh.SOURCE_TREE_ENV, "b" * 40)
    mapping = {
        ("rev-parse", "HEAD"): b"a" * 40,
        ("rev-parse", "HEAD^{tree}"): b"b" * 40,
        ("branch", "--show-current"): fresh.BRANCH.encode(),
        ("remote", "get-url", "origin"): fresh.ORIGIN.encode(),
        ("status", "--porcelain=v1", "--untracked-files=all"): b"",
        ("diff", "--cached", "--name-only"): b"",
        ("merge-base", fresh.BASE_HEAD, "HEAD"): fresh.BASE_HEAD.encode(),
        ("rev-parse", fresh.BASE_HEAD + "^{tree}"): fresh.BASE_TREE.encode(),
        ("rev-parse", "--show-toplevel"): str(ROOT).encode(),
        ("ls-files", "-v", "-z"): b"H source.py\0",
        ("ls-remote", "origin", "refs/heads/" + fresh.BRANCH): (
            "a" * 40 + "\trefs/heads/" + fresh.BRANCH
        ).encode(),
    }
    monkeypatch.setattr(fresh, "WORKTREE", ROOT)
    assert fresh.admit_source.__module__ == fresh.__name__
    keys = list(mapping)
    chosen = {
        "head": 0,
        "tree": 1,
        "branch": 2,
        "origin": 3,
        "status": 4,
        "index": 5,
        "base": 6,
        "root": 8,
        "flags": 9,
        "remote": 10,
    }
    monkeypatch.setattr(fresh, "_git", lambda *args: mapping[args])
    assert fresh.admit_source() == ("a" * 40, "b" * 40)
    if bad == "interlock":
        monkeypatch.setenv(fresh.REMOTE_HEAD_ENV, "wrong")
    else:
        mapping[keys[chosen[bad]]] = b"wrong"
    with pytest.raises(ValueError):
        fresh.admit_source()


@pytest.mark.parametrize("drift", [False, True])
def test_fresh_reconstructs_complete_exact_source_release(monkeypatch, tmp_path, drift):
    seed = accepted()
    for item in seed.bundle.files:
        if item.relative_path != "manifest.json":
            path = tmp_path / item.relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item.data)
    monkeypatch.setattr(fresh, "WORKTREE", tmp_path)
    observations = []

    def admit():
        observations.append(1)
        return (
            ("a" * 40, "b" * 40)
            if not drift or len(observations) == 1
            else ("c" * 40, "b" * 40)
        )

    monkeypatch.setattr(fresh, "admit_source", admit)
    rows = b"\0".join(
        b"100644 blob " + b"1" * 40 + b"\t" + name.encode()
        for name in seed.expected_source_paths
    )
    monkeypatch.setattr(fresh, "_git", lambda *args: rows)

    def collect(root, *, declaration):
        assert root == tmp_path
        assert (
            tuple(row.relative_path for row in declaration.source_inventory)
            == seed.expected_source_paths
        )
        assert (
            declaration.source_head == "a" * 40 and declaration.source_tree == "b" * 40
        )
        files = [
            item for item in seed.bundle.files if item.relative_path != "manifest.json"
        ]
        manifest = ReleaseFile("manifest.json", declaration.to_json().encode())
        return VerifiedRelease(
            ReleaseBundle(
                tuple(sorted((*files, manifest), key=lambda row: row.relative_path))
            ),
            manifest.sha256,
            "a" * 40,
            "b" * 40,
            seed.expected_source_paths,
        )

    monkeypatch.setattr(fresh, "collect_release_bundle", collect)
    if drift:
        with pytest.raises(fresh.ObservationDrift):
            fresh.reconstruct_release()
    else:
        release, binding = fresh.reconstruct_release()
        assert binding.verified_release == release
        assert binding.to_dict()["release_root"] == release_root(
            release.manifest.release_id
        )


def test_fresh_source_report_and_derivations_never_access_host(monkeypatch):
    release = accepted()
    monkeypatch.setattr(
        fresh, "reconstruct_release", lambda: (release, RuntimeBinding(release))
    )

    def forbidden(*args, **kwargs):
        pytest.fail("source-only report attempted filesystem/native operation")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    monkeypatch.setattr(d, "preflight", forbidden)
    monkeypatch.setattr(d, "execute_once", forbidden)
    monkeypatch.setattr(native, "materialize_release", forbidden)
    report = fresh.source_report()
    assert report == fresh.source_report()
    assert report["source_head"] == release.expected_source_head
    assert report["source_tree"] == release.expected_source_tree
    assert (
        report["manifest"]["source_inventory_sha256"]
        == release.manifest.source_inventory_sha256
    )
    assert report["release_id"] not in fresh.INCIDENT_RELEASE_IDS
    assert report["final_path"] == release_root(release.manifest.release_id)
    assert report["final_path"] not in fresh.INCIDENT_ROOTS
    assert fresh.attempt_path(release) == d.attempt_path(release)
    assert fresh.attempt_bytes(release) == d.attempt_bytes(release)
    for key in [
        "runtime_binding_eligible",
        "successor_soak_eligible",
        "execute_eligible",
    ]:
        assert report[key] is False
    assert (
        report["attempt_observation"] == report["final_path_observation"] == "NOT_RUN"
    )
    assert report["effect_disposition"] == "NOT_STARTED"
    assert report["automatic_retry"] == "NOT_AUTHORIZED"
    assert not hasattr(fresh, "preflight") and not hasattr(fresh, "execute_once")


@pytest.mark.parametrize(
    "head,tree", [(fresh.BASE_HEAD, "b" * 40), ("a" * 40, fresh.BASE_TREE)]
)
def test_fresh_source_generation_rejects_predecessor(monkeypatch, head, tree):
    monkeypatch.setenv(fresh.REMOTE_HEAD_ENV, head)
    monkeypatch.setenv(fresh.SOURCE_TREE_ENV, tree)
    with pytest.raises(ValueError, match="FRESH_SOURCE_REQUIRED"):
        fresh.admit_source()
    with pytest.raises(ValueError, match="HISTORICAL_RELEASE_FORBIDDEN"):
        fresh.attempt_path(accepted(head, tree))


@pytest.mark.parametrize("ordinal", range(3))
def test_fresh_source_rejects_every_incident_id(monkeypatch, ordinal):
    release = accepted()
    identifiers = list(fresh.INCIDENT_RELEASE_IDS)
    identifiers[ordinal] = release.manifest.release_id
    monkeypatch.setattr(fresh, "INCIDENT_RELEASE_IDS", tuple(identifiers))
    with pytest.raises(ValueError, match="HISTORICAL_RELEASE_FORBIDDEN"):
        fresh.attempt_bytes(release)


@pytest.mark.parametrize(
    "payload,absence,expected",
    [
        (None, True, "AVAILABLE"),
        (None, False, "INDETERMINATE"),
        (b"", False, "INDETERMINATE"),
        (b"{}", False, "INDETERMINATE"),
        ("exact", False, "CONSUMED"),
        ("exact", True, "INDETERMINATE"),
        ("old", False, "INDETERMINATE"),
        ("r1", False, "INDETERMINATE"),
    ],
)
def test_fresh_attempt_semantics_are_one_shot_and_release_bound(
    payload, absence, expected
):
    release = accepted()
    if payload == "exact":
        payload = fresh.attempt_bytes(release)
    elif payload == "old":
        payload = d.attempt_bytes(accepted("c" * 40, "e" * 40))
    elif payload == "r1":
        payload = (
            b'{"schema":"arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-attempt/v1",'
            b'"status":"CONSUMED"}'
        )
    assert fresh.classify_attempt(release, payload, absence_proven=absence) == expected


def test_fresh_source_registration_preserves_predecessors(monkeypatch):
    spec = runner._checkpoint_specs()[fresh.CHECKPOINT]
    assert spec.remote_branch == fresh.BRANCH
    assert spec.preflight is None and spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), fresh.BRANCH, "push")
        == fresh.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[fresh.CHECKPOINT] == "robinhood"
    assert runner._arch134_fresh_graph_check(ROOT) == ()
    assert runner._arch134_fresh_authority_check(ROOT) == ()
    for check in [
        runner._arch134_acl_authority_check,
        runner._arch134_d1s4_authority_check,
    ]:
        assert check(ROOT) == ()


@pytest.mark.parametrize(
    "payload",
    [
        (
            "from trading_bot.supervised_release.successor_direct_installation "
            "import execute_once"
        ),
        "from trading_bot.supervised_release import successor_native_direct_write",
        "from trading_bot import shared_namespace_acl_recovery",
        "from trading_bot.supervised_release import successor_publication_recovery",
        "from trading_bot.runtime import scheduler",
        "from trading_bot.robinhood import provider",
        "from trading_bot.arch133_rename import qualification",
        "os.rename()",
        "Path('fake').open('wb')",
        "SetSecurityInfo()",
        "Path.mkdir()",
        "Path.write_bytes()",
        "materialize_release()",
        "bind(library, 'MoveFileW', [], None)",
    ],
)
def test_fresh_source_graph_rejects_effects(monkeypatch, payload):
    original = Path.read_text

    def read(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        return result + "\n" + payload if path.name == "successor_source.py" else result

    monkeypatch.setattr(Path, "read_text", read)
    assert runner._arch134_fresh_graph_check(ROOT)


@pytest.mark.parametrize(
    "mapping",
    [
        "BLOB_PREDECESSORS",
        "BLOB_PINS",
        "AST_PREDECESSORS",
        "AST_PINS",
        "SOURCE_PINS",
        "NEW_AST_PINS",
    ],
)
def test_fresh_source_authority_fails_closed(monkeypatch, mapping):
    monkeypatch.setattr(runner, "ARCH134_FRESH_" + mapping, {})
    assert runner._arch134_fresh_authority_check(ROOT)


def test_fresh_exact_incident_inventory_and_python_declaration(monkeypatch):
    assert fresh.INCIDENT_RELEASE_IDS == (
        "release-18d5d329c1d458558e98d7effe523c3b",
        "release-cb94451fc3295a97afffe9fac5d09ff3",
        "release-03c42597246752319956ab96e01ed61c",
    )
    assert fresh.INCIDENT_ROOTS == tuple(
        release_root(identifier) + (".installing" if index else "")
        for index, identifier in enumerate(fresh.INCIDENT_RELEASE_IDS)
    )
    release = accepted()
    monkeypatch.setattr(fresh, "PYTHON_SHA256", "f" * 64)
    with pytest.raises(ValueError, match="PRODUCTION_PYTHON_DECLARATION_DRIFT"):
        fresh.attempt_path(release)


def test_fresh_current_docs_do_not_grant_executable_authority(monkeypatch):
    original = runner._git_blob_sha1

    def blob(path):
        if path.name in {"PROJECT_STATUS.md", "AI_TRADING_BOT_HANDOFF.md"}:
            pytest.fail("mutable current docs must not be executable blob pins")
        return original(path)

    monkeypatch.setattr(runner, "_git_blob_sha1", blob)
    assert runner._arch134_fresh_authority_check(ROOT) == ()


# Current source-selection contract; predecessor incident/host tests above stay exact.
def test_candidate_exact_freeze_and_successor_lineage():
    freeze = candidate.CandidateFreeze()
    assert freeze.candidate.to_dict() == {
        "repository": "callmedraken/ai-trading-bot",
        "reference": "develop",
        "head": "61836d6adadf25907c0347d42012bc4200a179ff",
        "tree": "eabbf166db2d14ce7fed603df3f8b6762394e3c7",
    }
    assert freeze.accepted_successor.head == "b18c6e32606828beeebc540a93c9f05e3e024323"
    assert freeze.accepted_successor.tree == "b082c15bc697bf289fc7997b3d7bf87050082dc3"
    assert freeze.accepted_successor.reference == fresh.BRANCH
    assert freeze.r1_state == "CONSUMED"
    assert candidate.INCIDENT_ROOTS == fresh.INCIDENT_ROOTS
    assert candidate.INCIDENT_RELEASE_IDS == fresh.INCIDENT_RELEASE_IDS
    assert freeze.to_bytes() == candidate.CandidateFreeze().to_bytes()
    assert (
        candidate.verify_candidate(
            freeze.to_bytes(), observed_develop=candidate.CANDIDATE
        )
        == freeze
    )
    from uuid import UUID

    assert UUID(freeze.candidate_id).version == 5


@pytest.mark.parametrize(
    "field,value",
    [
        ("head", "a" * 40),
        ("tree", "b" * 40),
        ("head", candidate.SUCCESSOR_HEAD),
        ("tree", candidate.SUCCESSOR_TREE),
        ("repository", "other/ai-trading-bot"),
        ("reference", "main"),
        ("reference", candidate.SUCCESSOR_REF),
    ],
)
def test_candidate_rejects_stale_wrong_source_and_repository(field, value):
    wrong = replace(candidate.CANDIDATE, **{field: value})
    with pytest.raises(ValueError, match="exact candidate"):
        candidate.CandidateFreeze(candidate=wrong)
    with pytest.raises(ValueError, match="stale or mismatched"):
        candidate.verify_candidate(
            candidate.CandidateFreeze().to_bytes(), observed_develop=wrong
        )


@pytest.mark.parametrize(
    "change",
    [
        {"accepted_successor": candidate.CANDIDATE},
        {"accepted_successor": replace(candidate.SUCCESSOR, tree="f" * 40)},
        {"r1_state": "AVAILABLE"},
        {"r1_state": "RECONCILED"},
        {"candidate": candidate.CANDIDATE.to_dict()},
    ],
)
def test_candidate_rejects_lineage_and_consumed_state_substitution(change):
    with pytest.raises(ValueError, match="exact candidate"):
        candidate.CandidateFreeze(**change)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{",
        b"null",
        b"[]",
        b"true",
        b"\xff",
        b"{}",
        b"x" * 16385,
        b"[" * 2000,
        candidate.CandidateFreeze().to_bytes().decode(),
        bytearray(candidate.CandidateFreeze().to_bytes()),
        candidate.CandidateFreeze().to_bytes() + b"\n",
        b"\xef\xbb\xbf" + candidate.CandidateFreeze().to_bytes(),
        json.dumps(candidate.CandidateFreeze().to_dict(), indent=2).encode(),
        candidate.CandidateFreeze()
        .to_bytes()
        .replace(b"{", b'{"schema":"duplicate",', 1),
    ],
)
def test_candidate_rejects_malformed_or_noncanonical_evidence(payload):
    with pytest.raises(ValueError):
        candidate.verify_candidate(payload, observed_develop=candidate.CANDIDATE)


@pytest.mark.parametrize("field", list(candidate.CandidateFreeze().to_dict()))
def test_candidate_evidence_cannot_change_any_frozen_policy_or_identity(field):
    from trading_bot.supervised_release.bundle import canonical_json

    evidence = candidate.CandidateFreeze().to_dict()
    evidence[field] = "SUBSTITUTED"
    with pytest.raises(ValueError):
        candidate.verify_candidate(
            canonical_json(evidence).encode(), observed_develop=candidate.CANDIDATE
        )


@pytest.mark.parametrize("release_id", candidate.INCIDENT_RELEASE_IDS)
@pytest.mark.parametrize("suffix", ["", ".installing", "\\child", "\\..\\fresh"])
def test_candidate_rejects_incident_identity_even_with_destination_alias(
    release_id, suffix
):
    with pytest.raises(ValueError):
        candidate.validate_destination(release_id, release_root(release_id) + suffix)


@pytest.mark.parametrize(
    "destination",
    [
        *candidate.INCIDENT_ROOTS,
        RELEASES_BASE,
        RELEASES_BASE + "\\..\\releases\\fresh",
        "F:/AITradingBot/releases/fresh",
        "\\\\?\\F:\\AITradingBot\\releases\\fresh",
    ],
)
def test_candidate_rejects_incident_or_noncanonical_destination(destination):
    with pytest.raises(ValueError):
        candidate.validate_destination(accepted().manifest.release_id, destination)


def test_candidate_destination_is_only_lexical_and_requires_later_host_review():
    release_id = accepted().manifest.release_id
    assert candidate.validate_destination(release_id, release_root(release_id)) is None
    design = candidate.readonly_admission_design(candidate.CandidateFreeze())
    assert design["production_namespace"] == RELEASES_BASE
    assert design["observer_implemented"] is False
    assert design["host_admission_pass"] is False
    assert design["write_authority"] is False
    assert design["materialization_eligible"] is False
    assert design["live_eligible"] is False
    assert design["later_review"] == "SUCCESSOR_ROOT_WRITE_AUTHORITY_AND_ACL_REVIEW"
    with pytest.raises(ValueError):
        candidate.readonly_admission_design({})


def test_candidate_future_sequence_and_no_effect_eligibility():
    data = candidate.CandidateFreeze().to_dict()
    assert data["selection"] == "SOURCE_ONLY_NOT_AN_INSTALLED_IMAGE"
    assert data["deployment_mode"] == "FRESH_SUCCESSOR_ONLY"
    assert data["future_sequence"] == [
        "terminal-green develop production candidate",
        "exact fresh-successor deployment-admission source",
        "ChatGPT exact-source acceptance",
        "develop integration + terminal gate",
        "local-main reconciliation",
        "real-host READ-ONLY deployment admission",
        "successor-root write-authority / ACL review",
        "separately reviewed protected fresh materialization",
        "manual-start fresh F1 successor soak",
        "fresh F1 evidence",
        "Architecture 145-B",
        "Research Results GUI",
        "large strategy campaigns",
    ]
    for key in (
        "incident_roots_authoritative",
        "consumed_generation_reuse",
        "historical_d1s4_r1_execute_substitution",
        "directory_namespace_promotion",
        "host_admission_executed",
        "materialization_eligible",
        "runtime_binding_eligible",
        "successor_soak_eligible",
        "scheduler_effects",
        "provider_effects",
        "broker_effects",
        "live_eligible",
        "later_steps_authorized",
    ):
        assert data[key] is False
    for name in (
        "preflight",
        "execute",
        "execute_once",
        "source_report",
        "admit_source",
    ):
        assert not hasattr(candidate, name)


def test_candidate_import_parse_verify_and_design_have_no_effects(monkeypatch):
    import socket
    import subprocess
    import sys
    from types import ModuleType

    source = Path(candidate.__file__).read_text(encoding="utf-8")
    payload = candidate.CandidateFreeze().to_bytes()
    isolated = ModuleType("candidate_no_effect_test")
    monkeypatch.setitem(sys.modules, isolated.__name__, isolated)

    def forbidden(*args, **kwargs):
        pytest.fail("pure deployment candidate attempted a host or external effect")

    with monkeypatch.context() as effects:
        effects.setattr(builtins, "open", forbidden)
        for method in (
            "open",
            "read_bytes",
            "read_text",
            "write_bytes",
            "write_text",
            "mkdir",
            "stat",
            "lstat",
            "resolve",
            "rename",
            "replace",
        ):
            effects.setattr(Path, method, forbidden)
        effects.setattr(subprocess, "run", forbidden)
        effects.setattr(socket, "socket", forbidden)
        effects.setattr(ctypes, "CDLL", forbidden)
        effects.setattr(d, "preflight", forbidden)
        effects.setattr(d, "execute_once", forbidden)
        effects.setattr(native, "materialize_release", forbidden)
        exec(compile(source, "<pure-candidate>", "exec"), isolated.__dict__)
        frozen = isolated.verify_candidate(payload, observed_develop=isolated.CANDIDATE)
        assert (
            isolated.readonly_admission_design(frozen)["host_admission_pass"] is False
        )
        release_id = "release-aaaaaaaaaaaa5aaa8aaaaaaaaaaaaaaa"
        isolated.validate_destination(release_id, release_root(release_id))


@pytest.mark.parametrize(
    "payload",
    [
        "import os",
        "import socket",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "from trading_bot.supervised_release import successor_source",
        "from trading_bot.supervised_release import successor_direct_installation",
        "from trading_bot.supervised_release import successor_publication_recovery",
        "from trading_bot.shared_namespace_acl_recovery import execute_once",
        "from trading_bot.runtime import scheduler",
        "__import__('os')",
        "open('host', 'w')",
        "Path.mkdir()",
        "os.rename()",
        "os.replace()",
        "SetFileInformationByHandle()",
        "FileRenameInfo()",
        "MoveFileExW()",
    ],
)
def test_candidate_source_guard_rejects_host_and_retired_dispatch(monkeypatch, payload):
    original = Path.read_text

    def read(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        return text + "\n" + payload if path.name == "deployment_candidate.py" else text

    monkeypatch.setattr(Path, "read_text", read)
    assert runner._deployment_candidate_graph_check(ROOT)


def test_candidate_exact_overlay_and_source_guard_preserve_frozen_predecessors(
    monkeypatch,
):
    assert runner._deployment_candidate_graph_check(ROOT) == ()
    assert runner._deployment_candidate_authority_check(ROOT) == ()
    assert runner._arch134_fresh_authority_check(ROOT) == ()
    assert runner._arch134_acl_authority_check(ROOT) == ()
    assert runner._arch134_d1s4_authority_check(ROOT) == ()
    assert runner._checkpoint_specs()[fresh.CHECKPOINT].preflight is None
    assert runner._checkpoint_specs()[fresh.CHECKPOINT].execute is None
    # This new source-only branch deliberately retains the reviewed broad route.
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(),
            "feature/robinhood-production-paper-fresh-successor-deployment-admission-current",
            "push",
        )
        is None
    )


@pytest.mark.parametrize(
    "mapping", ["BLOB_PREDECESSORS", "BLOB_PINS", "SOURCE_PINS", "AST_PINS"]
)
def test_candidate_overlay_map_mutation_fails_closed(monkeypatch, mapping):
    monkeypatch.setattr(runner, "DEPLOYMENT_CANDIDATE_" + mapping, {})
    assert runner._deployment_candidate_authority_check(ROOT)


def test_candidate_overlay_rejects_wrong_predecessor():
    with pytest.raises(ValueError, match="wrong exact predecessor"):
        runner._deployment_candidate_pin(
            "docs/AI_DEVELOPMENT_WORKFLOW.md", "0" * 40, ast_pin=False
        )


def test_candidate_current_docs_are_never_executable_blob_authority(monkeypatch):
    original = runner._git_blob_sha1

    def blob(path):
        if path.name in {"PROJECT_STATUS.md", "AI_TRADING_BOT_HANDOFF.md"}:
            pytest.fail("mutable current documents must not be blob-pinned")
        return original(path)

    monkeypatch.setattr(runner, "_git_blob_sha1", blob)
    assert runner._deployment_candidate_authority_check(ROOT) == ()


# Current fresh-successor observer. All host observations below are disposable
# fakes; the native production preflight is never invoked by source tests.
class ReadonlyFake(FakeHost):
    def __init__(self):
        from trading_bot.arch133_acl.read_only import TRADING_SID
        from trading_bot.arch133_verifier.token import TradingTokenObservation

        super().__init__(accepted())
        self.invocation = readonly.ReviewedInvocation(
            candidate.SourceIdentity(
                candidate.REPOSITORY, readonly.BRANCH, "c" * 40, "d" * 40
            ),
            TRADING_SID,
            False,
        )
        self.source_value = readonly.SourceObservation(
            self.invocation.observer,
            candidate.CANDIDATE,
            readonly.DESIGN,
            candidate.SUCCESSOR,
            readonly_source.manifest_for(self.release.manifest.source_inventory),
            "CONSUMED",
            readonly_source.CLOSURE_BLOB,
        )
        self.security_value = readonly.SecurityObservation(
            TradingTokenObservation(TRADING_SID, 1, False, False, ()),
            (("SeChangeNotifyPrivilege", 3),),
            "ACCESS_DENIED",
            None,
            0x1200A9,
            "e" * 64,
            (7, 13),
            (7, 14),
        )
        self.quiet_value = readonly.QuiescenceObservation((), "f" * 64, 0, True)
        self.namespace = ()
        self.source_count = 0
        self.drift = False

    @contextmanager
    def read_session(self, release_id):
        assert release_id == self.source_value.manifest.release_id
        self.events.append("read_scope")
        yield self

    def object(self, path, *, directory):
        assert path in ANCESTORS, "observer attempted a destination/incident open"
        self.events.append(("metadata", path))
        return self.nodes.get(path)

    def names(self, path):
        assert path == RELEASES_BASE
        self.events.append("parent_names")
        return self.namespace

    def namespace_metadata(self):
        return tuple(
            (name, index + 100, 0x10, "")
            for index, name in enumerate(self.names(RELEASES_BASE))
        )

    def source(self, invocation):
        assert invocation == self.invocation
        self.source_count += 1
        return self.source_value

    def security(self, parent):
        if self.drift and self.source_count > 1:
            return replace(self.security_value, parent_descriptor_sha256="a" * 64)
        return self.security_value

    def quiescence(self):
        return self.quiet_value

    def run(self):
        return readonly.admission(self.invocation, self, self)


def test_readonly_exact_lineage_pass_and_only_next_review_authority():
    fake = ReadonlyFake()
    result = fake.run()
    assert result["status"] == "PASS", result
    assert result["reason"] == readonly.READY
    assert result["manifest"]["source_head"] == candidate.CANDIDATE_HEAD
    assert result["manifest"]["source_tree"] == candidate.CANDIDATE_TREE
    assert result["source"]["design"]["head"] == readonly.DESIGN.head
    assert fake.source_count == 2 and fake.events.count("parent_names") == 2
    assert result["effects"] == dict.fromkeys(readonly.ZERO_EFFECTS, 0)
    assert result["authority"] == dict.fromkeys(readonly.NO_AUTHORITY, False)
    assert result["observations"]["security"]["sacl_status"] == "ACCESS_DENIED"
    readonly.verify_evidence(readonly.encode_evidence(result), expected=result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate", readonly.DESIGN),
        ("candidate", replace(candidate.CANDIDATE, head="f" * 40)),
        ("candidate", replace(candidate.CANDIDATE, tree="f" * 40)),
        ("candidate", replace(candidate.CANDIDATE, repository="wrong/repository")),
        ("observer", candidate.CANDIDATE),
        ("observer", replace(ReadonlyFake().invocation.observer, tree="a" * 40)),
        ("design", candidate.CANDIDATE),
        ("successor", candidate.CANDIDATE),
        ("r1_state", "AVAILABLE"),
        ("r1_state", "RECONCILED"),
        ("r1_state", "consumed"),
        ("closure_blob", "a" * 40),
    ],
)
def test_readonly_wrong_source_and_consumed_closure_block_before_host(field, value):
    fake = ReadonlyFake()
    fake.source_value = replace(fake.source_value, **{field: value})
    assert fake.run()["status"] == "BLOCKED"
    assert fake.events == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("production_python_version", "3.12.0"),
        ("production_python_sha256", "f" * 64),
        ("risk_policy_id", "other"),
        ("risk_policy_sha256", "f" * 64),
        ("strategy_config", MovingAverageCrossoverConfig(6, 20, Decimal("1"))),
        ("strategy_version", "2.0.0"),
        ("risk_policy_version", "2.0.0"),
    ],
)
def test_readonly_wrong_python_launcher_config_risk_identity(field, value):
    fake = ReadonlyFake()
    manifest = replace(fake.source_value.manifest, **{field: value})
    fake.source_value = replace(fake.source_value, manifest=manifest)
    assert fake.run()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "name",
    [
        *candidate.INCIDENT_RELEASE_IDS,
        *(item + ".installing" for item in candidate.INCIDENT_RELEASE_IDS),
        "RELEAS~1",
        "junction\\child",
        "alias.",
        "..",
        "alternate:stream",
    ],
)
def test_readonly_incident_alias_and_partial_names_never_traversed(name):
    fake = ReadonlyFake()
    fake.namespace = (name,)
    assert fake.run()["status"] == "BLOCKED"
    assert all(
        not isinstance(event, tuple) or event[1] in ANCESTORS for event in fake.events
    )


@pytest.mark.parametrize("suffix", ["", ".installing", ".partial", ".failed"])
def test_readonly_existing_final_or_partial_blocks_without_opening(suffix):
    fake = ReadonlyFake()
    fake.namespace = (fake.source_value.manifest.release_id + suffix,)
    assert fake.run()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "changes",
    [
        {"reparse": True},
        {"links": 2},
        {"filesystem": "ReFS"},
        {"local": False},
        {"persistent_acls": False},
        {"identity": (8, 55)},
        {"owner": "S-1-5-18"},
        {"protected": False},
        {"aces": ()},
    ],
)
def test_readonly_namespace_volume_owner_dacl_policy(changes):
    fake = ReadonlyFake()
    fake.nodes[RELEASES_BASE] = replace(fake.nodes[RELEASES_BASE], **changes)
    assert fake.run()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "changes",
    [
        {"elevated": True},
        {"thread_token_present": True},
        {"token_type": 2},
        {"user_sid": "S-1-5-21-999"},
        {"groups": ((ADMINISTRATORS_SID, 4),)},
    ],
)
def test_readonly_unreviewed_elevated_wrong_or_impersonating_token(changes):
    fake = ReadonlyFake()
    fake.security_value = replace(
        fake.security_value, token=replace(fake.security_value.token, **changes)
    )
    assert fake.run()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "changes",
    [
        {"privileges": (("SeDebugPrivilege", 2),)},
        {"sacl_status": "UNAVAILABLE"},
        {"sacl_status": "AVAILABLE", "sacl_sha256": None},
        {"sacl_sha256": "a" * 64},
        {"effective_parent_access": True},
        {"parent_descriptor_sha256": "raw descriptor or secret"},
    ],
)
def test_readonly_security_missing_or_unexpected_facts_block(changes):
    fake = ReadonlyFake()
    fake.security_value = replace(fake.security_value, **changes)
    assert fake.run()["status"] == "BLOCKED"


@pytest.mark.parametrize("status", ["ACCESS_DENIED", "PRIVILEGE_NOT_HELD", "AVAILABLE"])
def test_readonly_sacl_availability_explicit_without_enabling_privilege(status):
    fake = ReadonlyFake()
    fake.security_value = replace(
        fake.security_value,
        sacl_status=status,
        sacl_sha256="a" * 64 if status == "AVAILABLE" else None,
    )
    result = fake.run()
    assert result["status"] == "PASS"
    assert result["effects"]["privilege_enables"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"relevant_process_count": 1},
        {"reboot_manual_start": False},
        {"process_inventory_sha256": ""},
        {"tasks": (("raw command secret", "a" * 64),)},
    ],
)
def test_readonly_scheduler_runtime_and_resume_policy_fail_closed(changes):
    fake = ReadonlyFake()
    fake.quiet_value = replace(fake.quiet_value, **changes)
    assert fake.run()["status"] == "BLOCKED"


def test_readonly_security_drift_blocks_without_retry():
    fake = ReadonlyFake()
    fake.drift = True
    result = fake.run()
    assert result["status"] == "BLOCKED" and result["reason"] == "STABILITY"
    assert fake.source_count == 2


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"null",
        b"[" * 2000,
        b"\xff",
        b"x" * (readonly.MAX_EVIDENCE_BYTES + 1),
    ],
    ids=("empty", "object", "null", "deep", "utf8", "oversize"),
)
def test_readonly_malformed_oversize_evidence_rejected(payload):
    with pytest.raises(ValueError):
        readonly.verify_evidence(payload, expected=ReadonlyFake().run())


def test_readonly_evidence_sanitization_and_noncanonical_rejection():
    fake = ReadonlyFake()

    def fail(invocation):
        raise RuntimeError("secret=never-emit-provider-response")

    fake.source = fail
    result = fake.run()
    payload = readonly.encode_evidence(result)
    assert b"secret" not in payload and b"provider-response" not in payload
    for wrong in (
        payload + b"\n",
        b"\xef\xbb\xbf" + payload,
        json.dumps(result, indent=2).encode(),
        payload.replace(b"{", b'{"schema":"duplicate",', 1),
    ):
        with pytest.raises(ValueError):
            readonly.verify_evidence(wrong, expected=result)


@pytest.mark.parametrize(
    "identifier",
    ["release-aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa", "release-unknown", "../alias"],
)
def test_readonly_release_identity_requires_uuid5(identifier):
    with pytest.raises(ValueError):
        readonly.safe_namespace_names((), identifier)


@pytest.mark.parametrize(
    "args",
    [
        ("config", "--add", "key", "value"),
        ("fetch",),
        ("checkout", "develop"),
        ("remote", "set-url", "origin", "url"),
        ("cat-file", "--batch-command"),
        ("status", "--exec=bad"),
        ("rev-parse", "--resolve-git-dir=bad"),
    ],
)
def test_readonly_git_vocabulary_rejects_mutations_and_network_before_launch(
    monkeypatch, args
):
    def forbidden(*args, **kwargs):
        pytest.fail("forbidden Git vocabulary reached a process")

    monkeypatch.setattr(readonly_source.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="GIT_VOCABULARY"):
        readonly_source.LocalGitReader(Path("disposable")).query(*args)


def test_readonly_native_path_ceiling_rejects_incident_and_prospective_traversal():
    from trading_bot.supervised_release.deployment_admission_native import (
        ObservationPaths,
    )

    paths = ObservationPaths()
    for path in (
        *candidate.INCIDENT_ROOTS,
        release_root(ReadonlyFake().source_value.manifest.release_id),
        RELEASES_BASE + r"\alias",
        "F:/AITradingBot/releases",
    ):
        with pytest.raises(ValueError, match="READ_NAMESPACE_CEILING"):
            paths.admit(path)


def test_readonly_registration_is_additive_and_ci_owned(monkeypatch):
    specs = runner._checkpoint_specs()
    spec = specs[readonly.CHECKPOINT]
    assert spec.remote_branch == readonly.BRANCH and spec.execute is None
    assert spec.preflight is runner._readonly_admission_preflight
    assert (
        runner.resolve_ci_checkpoint(specs, readonly.BRANCH, "push")
        == readonly.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[readonly.CHECKPOINT] == "robinhood"
    assert runner._readonly_candidate_authority_check(ROOT) == ()
    assert (
        specs[fresh.CHECKPOINT].preflight is None
        and specs[fresh.CHECKPOINT].execute is None
    )


@pytest.mark.parametrize(
    "payload",
    [
        "import socket",
        "from trading_bot.supervised_release.successor_direct_installation "
        "import execute_once",
        "Path.mkdir()",
        "os.rename()",
        "SetSecurityInfo()",
        "AdjustTokenPrivileges()",
        "bind(x, 'MoveFileExW', [], None)",
    ],
)
def test_readonly_source_graph_rejects_effects_and_historical_substitution(
    monkeypatch, payload
):
    original = Path.read_text

    def read(path, *args, **kwargs):
        data = original(path, *args, **kwargs)
        return data + "\n" + payload if path.name == "deployment_admission.py" else data

    monkeypatch.setattr(Path, "read_text", read)
    assert runner._readonly_admission_graph_check(ROOT)


@pytest.fixture
def readonly_git(monkeypatch, tmp_path):
    def git_hash(kind, content):
        return hashlib.sha1(
            kind + b" " + str(len(content)).encode() + b"\0" + content
        ).hexdigest()

    def tree(entries):
        return git_hash(
            b"tree",
            b"".join(
                mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(oid)
                for mode, name, oid in entries
            ),
        )

    contents = {
        "pyproject.toml": b"project",
        LAUNCHER_RELATIVE_PATH: b"launcher",
        "src/trading_bot/__init__.py": b"",
    }
    objects = {name: git_hash(b"blob", content) for name, content in contents.items()}
    scripts_tree = tree(
        [
            (
                "100644",
                LAUNCHER_RELATIVE_PATH.split("/")[-1],
                objects[LAUNCHER_RELATIVE_PATH],
            )
        ]
    )
    package_tree = tree(
        [("100644", "__init__.py", objects["src/trading_bot/__init__.py"])]
    )
    source_tree = tree([("40000", "trading_bot", package_tree)])
    root_tree = tree(
        [
            ("100644", "pyproject.toml", objects["pyproject.toml"]),
            ("40000", "scripts", scripts_tree),
            ("40000", "src", source_tree),
        ]
    )
    selection = replace(candidate.CANDIDATE, tree=root_tree)
    monkeypatch.setattr(readonly_source, "CANDIDATE", selection)
    invocation = ReadonlyFake().invocation
    responses = {
        ("rev-parse", "--show-toplevel"): str(tmp_path).encode(),
        ("rev-parse", "--git-path", "info/grafts"): str(
            tmp_path / "missing-grafts"
        ).encode(),
        ("rev-parse", "HEAD"): invocation.observer.head.encode(),
        ("rev-parse", "HEAD^{tree}"): invocation.observer.tree.encode(),
        ("branch", "--show-current"): readonly.BRANCH.encode(),
        ("remote", "get-url", "origin"): readonly_source.ORIGIN.encode(),
        ("status", "--porcelain=v1", "--untracked-files=all"): b"",
        ("diff", "--cached", "--name-only"): b"",
        ("rev-parse", "--is-shallow-repository"): b"false",
        (
            "rev-parse",
            "refs/remotes/origin/" + readonly.BRANCH,
        ): invocation.observer.head.encode(),
        ("ls-files", "-v", "-z"): b"H file\0",
        (
            "config",
            "--local",
            "--get-regexp",
            r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
        ): b"",
        (
            "cat-file",
            "blob",
            readonly.DESIGN.head + ":" + readonly_source.CLOSURE_PATH,
        ): Path(candidate.__file__).read_bytes().replace(b"\r\n", b"\n"),
    }
    for identity in (selection, candidate.SUCCESSOR, readonly.DESIGN):
        responses[("rev-parse", identity.head + "^{tree}")] = identity.tree.encode()
        responses[("merge-base", identity.head, invocation.observer.head)] = (
            identity.head.encode()
        )
    responses[("merge-base", candidate.SUCCESSOR.head, selection.head)] = (
        candidate.SUCCESSOR.head.encode()
    )
    responses[("merge-base", selection.head, readonly.DESIGN.head)] = (
        selection.head.encode()
    )
    responses[("ls-tree", "-r", "-z", selection.head)] = b"".join(
        b"100644 blob " + objects[name].encode() + b"\t" + name.encode() + b"\0"
        for name in sorted(contents)
    )
    batch = b"".join(
        objects[name].encode()
        + b" blob "
        + str(len(contents[name])).encode()
        + b"\n"
        + contents[name]
        + b"\n"
        for name in sorted(contents)
    )

    class GitFake:
        root = tmp_path

        def query(self, *args, input_bytes=None):
            if args == ("cat-file", "--batch"):
                assert input_bytes == b"".join(
                    objects[name].encode() + b"\n" for name in sorted(contents)
                )
                return self.batch
            return self.responses[args]

    fake = GitFake()
    fake.responses, fake.batch, fake.invocation = responses, batch, invocation
    return fake


def test_readonly_git_exact_lineage_and_complete_candidate_inventory(readonly_git):
    value = readonly_source.observe_source(readonly_git, readonly_git.invocation)
    assert value.candidate.head == candidate.CANDIDATE_HEAD
    assert value.observer == readonly_git.invocation.observer
    assert len(value.manifest.source_inventory) == 3
    assert value.r1_state == "CONSUMED"


@pytest.mark.parametrize(
    "args,value",
    [
        (("rev-parse", "HEAD"), b"a" * 40),
        (("rev-parse", "HEAD^{tree}"), b"a" * 40),
        (("remote", "get-url", "origin"), b"wrong/repository"),
        (("status", "--porcelain=v1", "--untracked-files=all"), b" M changed"),
        (("ls-files", "-v", "-z"), b"h hidden\0"),
        (("rev-parse", "--is-shallow-repository"), b"true"),
    ],
)
def test_readonly_git_stale_wrong_dirty_and_hidden_index_rejected(
    readonly_git, args, value
):
    readonly_git.responses[args] = value
    with pytest.raises(ValueError):
        readonly_source.observe_source(readonly_git, readonly_git.invocation)


@pytest.mark.parametrize("mutation", ["missing", "blob", "extra", "closure"])
def test_readonly_complete_tree_and_blob_inventory_tampering(readonly_git, mutation):
    key = ("ls-tree", "-r", "-z", candidate.CANDIDATE_HEAD)
    if mutation == "missing":
        readonly_git.responses[key] = b"\0".join(
            readonly_git.responses[key].split(b"\0")[1:]
        )
    elif mutation == "blob":
        readonly_git.batch = readonly_git.batch.replace(b"launcher", b"mutated!")
    elif mutation == "extra":
        readonly_git.batch += b"unexpected"
    else:
        readonly_git.responses[
            (
                "cat-file",
                "blob",
                readonly.DESIGN.head + ":" + readonly_source.CLOSURE_PATH,
            )
        ] = b"not accepted closure"
    with pytest.raises(ValueError):
        readonly_source.observe_source(readonly_git, readonly_git.invocation)


def test_readonly_zero_mutation_and_external_effects(monkeypatch):
    import socket
    import subprocess

    from trading_bot.supervised_release.deployment_admission_native import (
        ObservationPaths,
    )

    fake = ReadonlyFake()

    def forbidden(*args, **kwargs):
        pytest.fail("read-only admission attempted an unauthorized effect")

    with monkeypatch.context() as effects:
        for name in (
            "mkdir",
            "write_bytes",
            "write_text",
            "rename",
            "replace",
            "unlink",
            "open",
        ):
            effects.setattr(Path, name, forbidden)
        effects.setattr(socket, "socket", forbidden)
        effects.setattr(subprocess, "run", forbidden)
        effects.setattr(d, "execute_once", forbidden)
        effects.setattr(native, "materialize_release", forbidden)
        assert fake.run()["status"] == "PASS"
        with pytest.raises(ValueError):
            ObservationPaths().admit(candidate.INCIDENT_ROOTS[0])


@pytest.mark.parametrize(
    "where", ["top", "source", "observations", "security", "token", "quiet", "ancestor"]
)
def test_readonly_evidence_schema_rejects_unrestricted_nested_fields(where):
    result = ReadonlyFake().run()
    targets = {
        "top": result,
        "source": result["source"],
        "observations": result["observations"],
        "security": result["observations"]["security"],
        "token": result["observations"]["security"]["token"],
        "quiet": result["observations"]["quiescence"],
        "ancestor": result["observations"]["ancestors"][0],
    }
    targets[where]["raw_secret_descriptor"] = "must not be emitted"
    with pytest.raises(ValueError):
        readonly.encode_evidence(result)


@pytest.mark.parametrize(
    "field,value",
    [("production_writes", 1), ("directory_creations", False), ("provider_calls", "0")],
)
def test_readonly_evidence_cannot_claim_effectful_pass(field, value):
    result = ReadonlyFake().run()
    result["effects"][field] = value
    with pytest.raises(ValueError):
        readonly.encode_evidence(result)


@pytest.mark.parametrize("mutation", ["bytes", "version", "writable", "alias", "drift"])
def test_readonly_native_python_collector_failures_use_only_disposable_facts(
    monkeypatch, mutation
):
    from trading_bot.supervised_release import deployment_admission_native as n

    fake = FakeHost(accepted())
    monkeypatch.setattr(n, "PYTHON_SHA256", hashlib.sha256(FAKE_PYTHON).hexdigest())
    if mutation == "bytes":
        fake.data[PRODUCTION_PYTHON] = b"wrong binary"
    elif mutation == "version":
        fake.python_version = lambda: "3.12.0"
    elif mutation == "writable":
        fake.nodes[PRODUCTION_PYTHON] = replace(
            fake.nodes[PRODUCTION_PYTHON], owner="S-1-5-21-999"
        )
    elif mutation == "alias":
        fake.nodes[PRODUCTION_PYTHON] = replace(fake.nodes[PRODUCTION_PYTHON], links=2)
    else:
        original = fake.object
        count = 0

        def drift(path, **kwargs):
            nonlocal count
            count += 1
            row = original(path, **kwargs)
            return replace(row, identity=(7, 999)) if count > 2 else row

        fake.object = drift
    with pytest.raises(ValueError):
        n.observe_python(fake, 7)


def test_readonly_native_binary_read_rewinds_only_held_read_handle(monkeypatch):
    from trading_bot.supervised_release import deployment_admission_native as n
    from trading_bot.supervised_release import native_read

    session = object.__new__(n.AdmissionReadSession)
    session.kernel = object()
    session.handles = {PRODUCTION_PYTHON: 77}
    calls = []

    def binder(library, name, args, result):
        assert library is session.kernel and name == "SetFilePointerEx"

        def rewind(handle, offset, output, origin):
            calls.append((handle, offset, output, origin))
            return True

        return rewind

    monkeypatch.setattr(n, "bind", binder)
    monkeypatch.setattr(
        native_read.WindowsReadSession, "read", lambda *args: FAKE_PYTHON
    )
    assert session.read(PRODUCTION_PYTHON, n.MAX_FILE_BYTES) == FAKE_PYTHON
    assert session.read(PRODUCTION_PYTHON, n.MAX_FILE_BYTES) == FAKE_PYTHON
    assert calls == [(77, 0, None, 0)] * 2
    with pytest.raises(ValueError):
        session.read(candidate.INCIDENT_ROOTS[0], n.MAX_FILE_BYTES)


def test_readonly_diagnostic_transport_is_fixed_bounded_and_sanitized(monkeypatch):
    from trading_bot.supervised_release import deployment_admission_native as n

    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[:6] == (
            n.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        )
        assert str(argv[6]).endswith("arch134_deployment_admission_observe.ps1")
        assert kwargs == {"capture_output": True, "check": False, "timeout": 60}
        return SimpleNamespace(
            returncode=0,
            stderr=b"",
            stdout=b'{"schema":"arch134-deployment-quiescence/v1","tasks":[],"process_inventory_sha256":"'
            + b"f" * 64
            + b'","relevant_process_count":0,"reboot_manual_start":true}',
        )

    monkeypatch.setattr(n.subprocess, "run", run)
    result = n.observe_quiescence(Path("disposable-source"))
    readonly.require_quiescence(result)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mapping",
    [
        "READONLY_BLOB_BEFORE",
        "READONLY_BLOB_AFTER",
        "READONLY_SOURCE_PINS",
        "READONLY_AST_PINS",
    ],
)
def test_readonly_additive_maps_and_registration_fail_closed(monkeypatch, mapping):
    monkeypatch.setattr(runner, mapping, {})
    assert runner._readonly_candidate_authority_check(ROOT)


def test_readonly_historical_execute_substitution_rejected(monkeypatch):
    old = runner._checkpoint_specs

    def specs():
        values = old()
        values[readonly.CHECKPOINT] = replace(
            values[readonly.CHECKPOINT], execute=d.execute_once
        )
        return values

    monkeypatch.setattr(runner, "_checkpoint_specs", specs)
    assert runner._readonly_candidate_authority_check(ROOT)


@pytest.mark.parametrize(
    "mutation",
    ["reparse", "short_alias", "duplicate_id", "not_directory", "changed_id"],
)
def test_readonly_parent_metadata_rejects_aliases_and_identity_drift(mutation):
    fake = ReadonlyFake()
    sibling = "release-aaaaaaaaaaaa5aaa8aaaaaaaaaaaaaaa"
    rows = ((sibling, 500, 0x10, ""),)
    if mutation == "reparse":
        rows = ((sibling, 500, 0x410, ""),)
    elif mutation == "short_alias":
        rows = ((sibling, 500, 0x10, "RELEAS~1"),)
    elif mutation == "duplicate_id":
        rows += (("release-bbbbbbbbbbbb5bbb8bbbbbbbbbbbbbbb", 500, 0x10, ""),)
    elif mutation == "not_directory":
        rows = ((sibling, 500, 0, ""),)

    def metadata():
        if mutation == "changed_id" and fake.source_count > 1:
            return ((sibling, 501, 0x10, ""),)
        return rows

    fake.namespace_metadata = metadata
    assert fake.run()["status"] == "BLOCKED"
    assert fake.source_count <= 2


def test_readonly_parent_metadata_parser_never_opens_a_child():
    from trading_bot.supervised_release.deployment_admission_native import (
        parse_namespace_page,
    )

    name = candidate.INCIDENT_RELEASE_IDS[0]
    encoded = name.encode("utf-16-le")
    raw = bytearray(65536)
    raw[56:60] = (0x410).to_bytes(4, "little")
    raw[60:64] = len(encoded).to_bytes(4, "little")
    raw[96:104] = (77).to_bytes(8, "little")
    raw[104 : 104 + len(encoded)] = encoded
    assert parse_namespace_page(bytes(raw)) == ((name, 77, 0x410, ""),)
    raw[68] = 25
    with pytest.raises(ValueError):
        parse_namespace_page(bytes(raw))


def test_readonly_existing_canonical_sibling_is_observed_without_traversal():
    fake = ReadonlyFake()
    fake.namespace = ("release-aaaaaaaaaaaa5aaa8aaaaaaaaaaaaaaa",)
    assert fake.run()["status"] == "PASS"


@pytest.mark.parametrize("changed", ["source", "python", "scheduler", "token"])
def test_readonly_every_repeated_observation_blocks_on_drift(changed):
    fake = ReadonlyFake()
    if changed == "source":
        original = fake.source

        def source(invocation):
            result = original(invocation)
            return (
                replace(result, observer=replace(result.observer, tree="e" * 40))
                if fake.source_count == 2
                else result
            )

        fake.source = source
    elif changed == "scheduler":
        fake.quiescence = lambda: (
            replace(fake.quiet_value, process_inventory_sha256="a" * 64)
            if fake.source_count == 2
            else fake.quiet_value
        )
    else:

        def security(parent):
            result = fake.security_value
            if fake.source_count == 2:
                if changed == "python":
                    result = replace(result, python_identity=(7, 999))
                else:
                    result = replace(
                        result, token=replace(result.token, groups=(("S-1-5-18", 4),))
                    )
            return result

        fake.security = security
    result = fake.run()
    assert result["status"] == "BLOCKED" and result["reason"] == "STABILITY"
    assert fake.source_count == 2


def test_readonly_evidence_root_rejects_production_before_metadata_or_dispatch(
    monkeypatch,
):
    spec = runner._checkpoint_specs()[readonly.CHECKPOINT]
    monkeypatch.setattr(
        runner, "_readonly_candidate_authority_check", spec.authority_check
    )
    original_specs = runner._checkpoint_specs
    monkeypatch.setattr(runner, "_readonly_candidate_authority_check", lambda root: ())
    # Keep the exact admitted registration while making the authority observation
    # a fake. The real preflight callback must never be reached by this test.
    monkeypatch.setattr(
        runner,
        "_checkpoint_specs",
        lambda: {**original_specs(), readonly.CHECKPOINT: spec},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("production metadata/host dispatch reached")

    monkeypatch.setattr(runner, "_PRE_READONLY_PREFLIGHT", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    with pytest.raises(RuntimeError, match="external evidence"):
        runner._readonly_preflight_checkpoint(
            spec,
            repo_root=ROOT,
            evidence_root=Path(RELEASES_BASE) / "forbidden-evidence",
        )
