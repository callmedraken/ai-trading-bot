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
from trading_bot.supervised_release import successor_direct_installation as d
from trading_bot.supervised_release import successor_native_direct_write as native
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


def test_registered_forward_dispatch_and_authority():
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
