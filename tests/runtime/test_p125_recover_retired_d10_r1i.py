"""Incident-specific source/fake-boundary tests; no protected host is accessed."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import inspect
import io
import json
import ntpath
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import d10_protected_deployment as d
from scripts import d10_protected_replacement as r
from scripts import d10_protected_replacement_windows as w
from scripts import p125_recover_retired_d10_r1i as op
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_SIGNING_KEY_ID,
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Verifier:
    key_id = D10_SIGNING_KEY_ID
    valid = True

    def verify(self, message: bytes, signature: bytes) -> bool:
        return self.valid and bool(message and signature)


class Native:
    _allowed = staticmethod(w._WindowsReplacementReader._allowed)

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.directories: dict[str, tuple[str, ...]] = {}
        self.changes: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, str]] = []
        self.absence_ambiguous = False
        self.scheduler_changes: dict[str, object] = {}
        self.verifier = Verifier()

    def identity(self, path: str, directory: bool) -> d.NativeObject:
        owner, protected, aces = (
            d.expected_parent_policy()
            if path == r.PARENT_PATH
            else d.expected_policy(directory)
        )
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
            1000 + len(path),
            1,
            0 if directory else len(self.files[path]),
        )
        return replace(item, **self.changes.get(path, {}))

    def require_administrator(self) -> None:
        self.calls.append(("administrator", ""))

    def list_directory(self, path: str) -> d.CheckedDirectory:
        self.calls.append(("directory", path))
        return d.CheckedDirectory(
            self.identity(path, True), self.directories[path], True
        )

    def read_file(self, path: str, limit: int) -> d.CheckedFile:
        self.calls.append(("file", path))
        assert len(self.files[path]) <= limit
        return d.CheckedFile(self.identity(path, False), self.files[path], True)

    def absent(self, path: str) -> bool:
        self.calls.append(("absent", path))
        if not self._allowed(path, directory=None):
            raise w.AdmissionBlocked("native_path_unreviewed")
        return path not in self.files and path not in self.directories

    def absent_typed(self, path: str, *, directory: bool) -> bool:
        self.calls.append(("absent_typed", path))
        assert type(directory) is bool
        assert self._allowed(path, directory=directory)
        if self.absence_ambiguous:
            raise w.AdmissionBlocked("typed_open_unavailable")
        return path not in self.files and path not in self.directories

    def remove(self, path: str) -> None:
        self.files.pop(path, None)
        self.directories.pop(path, None)
        parent, leaf = ntpath.dirname(path), ntpath.basename(path)
        self.directories[parent] = tuple(
            name for name in self.directories[parent] if name != leaf
        )

    def scheduler(self, command, **kwargs):
        assert command == (
            w.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(w.SCHEDULER_HELPER),
        )
        assert kwargs == {"capture_output": True, "check": False, "timeout": 30}
        read = {
            **w._EXPECTED_SCHEDULER,
            "xml_byte_length": 83,
            "xml_sha256": "a" * 64,
            **self.scheduler_changes,
        }
        record = {
            "schema": w.SCHEDULER_SCHEMA,
            "status": "OBSERVED",
            "first": read,
            "second": read,
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(record).encode(), b"")

    def observe(self) -> w.CleanupObservation:
        return w._observe_cleanup(self, self.verifier, self.scheduler)


@pytest.fixture
def full(monkeypatch: pytest.MonkeyPatch) -> tuple[Native, r.RetiredCleanupPlan]:
    """Synthetic signed material with the frozen 306-file/337-target shape."""
    source_files = {
        r.R1I_MISSING_RELATIVE_TARGET[len("source\\") :].replace("\\", "/"): b"soak",
        "src/trading_bot/__init__.py": b"package",
        **{
            f"src/trading_bot/p{i % 22:02d}/m{i:03d}.py": f"file{i}".encode()
            for i in range(304)
        },
    }
    manifest = ExecutableManifest(
        EXECUTABLE_MANIFEST_SCHEMA,
        tuple(
            ExecutableManifestEntry(path, len(data), _digest(data))
            for path, data in sorted(source_files.items())
        ),
    )
    native = Native()
    native.directories[r.PARENT_PATH] = tuple(
        sorted(
            (
                ntpath.basename(r.CANONICAL_PATH),
                ntpath.basename(r.RETIRED_PATH),
            )
        )
    )
    for root, name, guard in (
        (r.RETIRED_PATH, "OLD_IDENTITY", b"old guard"),
        (r.CANONICAL_PATH, "NEW_IDENTITY", b"new guard"),
    ):
        original = getattr(r, name)
        attestation = build_deployment_attestation(
            certified_source_head=r.NEW_IDENTITY.certified_source_head,
            certified_source_tree=r.NEW_IDENTITY.certified_source_tree,
            production_python_version="3.14.3",
            launch_guard_byte_length=len(guard),
            launch_guard_sha256=_digest(guard),
            executable_manifest_sha256=manifest.digest,
            executable_file_count=len(manifest.entries),
        ).canonical_bytes()
        signature = (1).to_bytes(32, "big") * 2
        monkeypatch.setattr(
            r,
            name,
            replace(
                original,
                deployment_id=json.loads(attestation)["deployment_id"],
                manifest_sha256=manifest.digest,
                executable_file_count=len(manifest.entries),
                executable_total_bytes=sum(len(data) for data in source_files.values()),
                guard_byte_length=len(guard),
                guard_sha256=_digest(guard),
                unsigned_attestation_sha256=_digest(attestation),
                detached_signature_sha256=_digest(signature)
                if name == "OLD_IDENTITY"
                else None,
            ),
        )
        native.files.update(
            {
                root + r"\launch-guard.py": guard,
                root + r"\executable-manifest.json": manifest.canonical_bytes(),
                root + r"\deployment.attestation.json": attestation,
                root + r"\deployment.attestation.sig": signature,
                **{
                    root + "\\source\\" + path.replace("/", "\\"): data
                    for path, data in source_files.items()
                },
            }
        )
    children: dict[str, set[str]] = {}
    for path in native.files:
        current = path
        while current != r.PARENT_PATH:
            parent, leaf = ntpath.dirname(current), ntpath.basename(current)
            children.setdefault(parent, set()).add(leaf)
            current = parent
    native.directories.update(
        {path: tuple(sorted(names)) for path, names in children.items()}
    )
    observation = native.observe()
    assert observation.state is r.CleanupState.FULL_RETIRED
    assert len(observation.plan.targets) == 337
    return native, observation.plan


@pytest.fixture
def partial(full) -> tuple[Native, w.CleanupObservation]:
    native, plan = full
    native.remove(plan.targets[0].path)
    observation = native.observe()
    assert observation.state is r.CleanupState.PARTIAL_RETIRED
    return native, observation


class Deletion(w._FixedRetiredDeletionNative):
    """Fake every effect seam while running the real frozen commit proof."""

    def __init__(self, native: Native, plan: r.RetiredCleanupPlan):
        self.data = native
        self._plan = plan
        self._targets = {target.path: target for target in plan.targets}
        self.handles: dict[int, tuple[str, bool]] = {}
        self.pending: str | None = None
        self.events: list[str] = []
        self.deleted_indices: list[int] = []
        self.failure = ""
        self.last_error = -1
        self.native_success = False

    def _cleanup_open(self, path: str, *, parent: bool, directory: bool) -> int:
        self.events.append("parent_open" if parent else "target_open")
        assert path != self._plan.targets[0].path or self.failure == "historical"
        if not parent:
            self.deleted_indices.append(self._plan.targets.index(self._targets[path]))
        handle = 1 if parent else 2
        self.handles[handle] = (path, directory)
        return handle

    def _inspect(self, handle: int, path: str) -> d.NativeObject:
        assert self.handles[handle][0] == path
        item = self.data.identity(path, self.handles[handle][1])
        if self.failure == "parent_identity" and self.native_success and handle == 1:
            return replace(item, file_index=item.file_index + 1)
        return item

    def _pinned_names(self, handle: int) -> tuple[str, ...]:
        names = self.data.directories[self.handles[handle][0]]
        if self.failure == "parent_inventory" and self.native_success:
            return names + ("unexpected",)
        return names

    def _pinned_file(self, handle: int, size: int) -> bytes:
        data = self.data.files[self.handles[handle][0]]
        return data + b"drift" if self.failure == "pre_call" else data

    def _set_disposition(self, handle: int) -> bool:
        self.events.append("disposition")
        if self.failure in ("native_false", "native_false_parent_close"):
            return False
        self.pending = self.handles[handle][0]
        self.native_success = True
        return True

    def _close(self, handle: int) -> None:
        self.events.append("target_close" if handle == 2 else "parent_close")
        self.last_error = 999
        if handle == 2 and self.pending is not None:
            self.data.remove(self.pending)
            self.pending = None
        if (
            handle == 2
            and self.failure == "target_close"
            or handle == 1
            and self.failure in ("parent_close", "native_false_parent_close")
        ):
            raise w.AdmissionBlocked("private raw exception must not escape")
        del self.handles[handle]

    def absent_typed(self, path: str, *, directory: bool) -> bool:
        self.events.append("typed_absence")
        if self.failure == "absence":
            return False
        if self.failure == "historical":
            return self.data.absent(path)
        return self.data.absent_typed(path, directory=directory)


class Operations:
    def __init__(self, native: Native, observation: w.CleanupObservation):
        self.data = native
        self.observation = observation
        self.backend = Deletion(native, observation.plan)
        self.session = w._FixedRetiredRecoverySession(observation, self.backend)
        self.post_calls = 0

    def begin_fixed_retired_recovery_session(self):
        return self.observation, self.session

    def observe_retired_cleanup_post(self) -> bool:
        self.post_calls += 1
        return self.data.observe().state is r.CleanupState.RETIRED_ABSENT


def test_exact_source_owned_incident_and_historical_identity() -> None:
    assert r.R1I_PLAN_TARGET_COUNT == 337
    assert r.R1I_MISSING_PREFIX_COUNT == 1
    assert r.R1I_MISSING_RELATIVE_TARGET == (
        r"source\scripts\run_personal_desktop_unattended_one_week_soak.py"
    )
    assert r.OLD_IDENTITY.manifest_sha256 == (
        "e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a"
    )
    assert r.OLD_IDENTITY.detached_signature_sha256 == (
        "7ae83e28bcd8ab7cb59ab990a7f3b3191f485621aa83f5431f7f25fc32c8b4eb"
    )
    assert r.OLD_IDENTITY.executable_file_count == 306
    assert not inspect.signature(w.begin_fixed_retired_recovery_session).parameters
    assert list(inspect.signature(op.run_recovery).parameters) == ["operations"]


@pytest.mark.parametrize("directory", [False, True])
def test_generic_source_absence_rejected_and_typed_open_exact(directory, monkeypatch):
    reader = object.__new__(w._WindowsReplacementReader)
    path = r.RETIRED_PATH + (
        r"\source\scripts" if directory else "\\" + r.R1I_MISSING_RELATIVE_TARGET
    )
    calls = []
    reader._kernel = object()
    reader._bind = lambda *args: (
        lambda *values: calls.append(values) or ctypes.c_void_p(-1).value
    )
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 2)
    with pytest.raises(w.AdmissionBlocked, match="native_path_unreviewed"):
        reader.absent(path)
    assert not calls
    assert reader.absent_typed(path, directory=directory) is True
    assert calls[0][0] == path
    assert calls[0][4] == w._OPEN_EXISTING
    assert calls[0][5] & w._FILE_FLAG_OPEN_REPARSE_POINT
    assert bool(calls[0][5] & w._FILE_FLAG_BACKUP_SEMANTICS) is directory


@pytest.mark.parametrize(
    "error,absent", [(2, True), (3, True), (5, False), (32, False), (87, False)]
)
@pytest.mark.parametrize("directory", [False, True])
def test_typed_absence_accepts_only_positive_not_found(
    error, absent, directory, monkeypatch
):
    reader = object.__new__(w._WindowsReplacementReader)
    reader._kernel = object()
    reader._bind = lambda *args: lambda *values: ctypes.c_void_p(-1).value
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error)
    path = r.RETIRED_PATH + r"\source\scripts" + ("" if directory else "\\a.py")
    if absent:
        assert reader.absent_typed(path, directory=directory) is True
    else:
        with pytest.raises(w.AdmissionBlocked, match="native_open_unavailable"):
            reader.absent_typed(path, directory=directory)
    # Ordinary typed reads retain their original fail-closed open behavior.
    with pytest.raises(w.AdmissionBlocked):
        reader._open(path, directory=directory)


@pytest.mark.parametrize("kind", [None, 0, 1, "file", object()])
def test_typed_absence_requires_bool(kind):
    reader = object.__new__(w._WindowsReplacementReader)
    with pytest.raises(w.AdmissionBlocked, match="native_object_kind_unreviewed"):
        reader.absent_typed(
            r.RETIRED_PATH + "\\" + r.R1I_MISSING_RELATIVE_TARGET, directory=kind
        )


@pytest.mark.parametrize(
    "path",
    [
        r"F:\Other\a.py",
        r.RETIRED_PATH + r"\source\..\a.py",
        r.RETIRED_PATH + r"\source\scripts\a.py:stream",
    ],
)
def test_typed_absence_retains_fixed_path_admission(path):
    reader = object.__new__(w._WindowsReplacementReader)
    with pytest.raises(w.AdmissionBlocked, match="native_path_unreviewed"):
        reader.absent_typed(path, directory=False)


@pytest.mark.parametrize("directory", [False, True])
def test_typed_present_object_and_close_ambiguity_are_not_absence(directory):
    reader = object.__new__(w._WindowsReplacementReader)
    calls = []
    reader._open = lambda path, **kwargs: calls.append(kwargs) or 5
    reader._close = lambda handle: calls.append(handle)
    assert reader.absent_typed(r.RETIRED_PATH, directory=directory) is False
    assert calls == [{"directory": directory, "absence_probe": True}, 5]

    def ambiguous(handle):
        raise w.AdmissionBlocked("close")

    reader._close = ambiguous
    with pytest.raises(w.AdmissionBlocked):
        reader.absent_typed(r.RETIRED_PATH, directory=directory)


def test_historical_r1e_defect_and_corrected_partial_classification(full, monkeypatch):
    native, plan = full
    observation = native.observe()
    backend = Deletion(native, plan)
    backend.failure = "historical"
    session = w._FixedRetiredCleanupSession(observation, backend)
    assert session.delete_next() is r.MutationOutcome.INDETERMINATE
    assert session.completed_targets == 0
    assert plan.targets[0].path not in native.files
    assert session.delete_diagnostic.stage is r.DeleteFailureStage.POST_CALL_VERIFY
    typed = native.absent_typed
    monkeypatch.setattr(
        native, "absent_typed", lambda path, **kwargs: native.absent(path)
    )
    assert native.observe().state is r.CleanupState.CONFLICTING
    monkeypatch.setattr(native, "absent_typed", typed)
    corrected = native.observe()
    assert corrected.state is r.CleanupState.PARTIAL_RETIRED
    assert corrected.missing_indices == (0,)
    w._require_retired_recovery(corrected)
    with pytest.raises(w.AdmissionBlocked):
        session.delete_next()


def test_exact_prefix_double_admission_before_native_construction(partial, monkeypatch):
    native, observation = partial
    native.calls.clear()
    monkeypatch.setattr(w, "_WindowsReplacementReader", lambda: native)
    monkeypatch.setattr(w, "WindowsCngVerifier", lambda: native.verifier)
    monkeypatch.setattr(w, "_run_scheduler_bounded", native.scheduler)

    def constructed(plan):
        assert native.calls.count(("administrator", "")) == 2
        assert plan == observation.plan
        return Deletion(native, plan)

    monkeypatch.setattr(w, "_FixedRetiredDeletionNative", constructed)
    read, session = w.begin_fixed_retired_recovery_session()
    assert read == observation
    assert session.completed_targets == 1
    assert read.missing_indices == (0,)
    assert read.plan == observation.plan
    assert (
        len(
            {
                item.path
                for item in read.admitted_objects
                if item.path.startswith(r.RETIRED_PATH)
            }
        )
        == 336
    )


@pytest.mark.parametrize(
    "missing", [(), (1,), (0, 1), (0, 3), (3, 5), (0, 306), (0, 309)]
)
def test_arbitrary_nonprefix_extra_or_full_states_block(full, missing):
    native, plan = full
    for index in missing:
        native.remove(plan.targets[index].path)
    observation = native.observe()
    with pytest.raises((w.AdmissionBlocked, ValueError)):
        w._require_retired_recovery(observation)


def test_retired_absent_is_not_recovery(full):
    native, plan = full
    for target in plan.targets:
        native.remove(target.path)
    observation = native.observe()
    assert observation.state is r.CleanupState.RETIRED_ABSENT
    with pytest.raises(w.AdmissionBlocked):
        w._require_retired_recovery(observation)


@pytest.mark.parametrize(
    "change",
    [
        "unexpected",
        "case",
        "bytes",
        "size",
        "acl",
        "reparse",
        "links",
        "final_path",
        "volume",
        "trust",
        "signature",
        "staging",
        "sibling",
        "parent",
        "canonical_unsigned",
        "canonical_bytes",
        "canonical_guard",
        "canonical_manifest",
        "canonical_attestation",
        "lease",
        "installing",
        "tmp",
        "cache",
        "scheduler",
        "ambiguous",
    ],
)
def test_recovery_preserves_all_protected_admission_requirements(partial, change):
    native, observation = partial
    path = observation.plan.targets[1].path
    canonical = r.CANONICAL_PATH
    if change == "unexpected":
        native.directories[ntpath.dirname(path)] += ("unexpected",)
    elif change == "case":
        parent, leaf = ntpath.dirname(path), ntpath.basename(path)
        native.directories[parent] = tuple(
            name.upper() if name == leaf else name
            for name in native.directories[parent]
        )
    elif change == "bytes":
        native.files[path] = b"X" + native.files[path][1:]
    elif change == "size":
        native.changes[path] = {"size": len(native.files[path]) + 1}
    elif change in ("acl", "reparse", "links", "final_path", "volume"):
        key, value = {
            "acl": ("aces", ()),
            "reparse": ("reparse", True),
            "links": ("links", 2),
            "final_path": ("final_path", r"F:\Other"),
            "volume": ("volume_serial", 18),
        }[change]
        native.changes[path] = {key: value}
    elif change == "trust":
        native.files[r.RETIRED_PATH + r"\deployment.attestation.json"] += b" "
    elif change == "signature":
        native.verifier.valid = False
    elif change in ("staging", "sibling"):
        native.directories[r.PARENT_PATH] += (
            ntpath.basename(r.STAGING_PATH)
            if change == "staging"
            else "D10.retired-unexpected",
        )
    elif change == "parent":
        native.changes[r.PARENT_PATH] = {"aces": ()}
    elif change == "canonical_unsigned":
        native.remove(canonical + r"\deployment.attestation.sig")
    elif change.startswith("canonical_"):
        relative = {
            "canonical_bytes": "\\" + r.R1I_MISSING_RELATIVE_TARGET,
            "canonical_guard": r"\launch-guard.py",
            "canonical_manifest": r"\executable-manifest.json",
            "canonical_attestation": r"\deployment.attestation.json",
        }[change]
        native.files[canonical + relative] += b"X"
    elif change in ("lease", "installing", "tmp", "cache"):
        name = {
            "lease": "activation.lease.json",
            "installing": "activation.lease.json.installing",
            "tmp": "activation.lease.json.tmp",
            "cache": "no-pycache",
        }[change]
        native.files[canonical + "\\" + name] = b"conflict"
    elif change == "scheduler":
        native.scheduler_changes["enabled"] = False
    else:
        native.absence_ambiguous = True
    assert native.observe().state is r.CleanupState.CONFLICTING


@pytest.mark.parametrize("drift", ["identity", "missing", "scheduler"])
def test_matching_two_full_reads_required(partial, monkeypatch, drift):
    native, observation = partial
    native.calls.clear()
    original = native.require_administrator

    def administrator():
        original()
        if native.calls.count(("administrator", "")) == 2:
            if drift == "identity":
                native.changes[observation.plan.targets[1].path] = {"file_index": 4000}
            elif drift == "missing":
                native.remove(observation.plan.targets[1].path)
            else:
                native.scheduler_changes["xml_sha256"] = "b" * 64

    monkeypatch.setattr(native, "require_administrator", administrator)
    monkeypatch.setattr(w, "_WindowsReplacementReader", lambda: native)
    monkeypatch.setattr(w, "WindowsCngVerifier", lambda: native.verifier)
    monkeypatch.setattr(w, "_run_scheduler_bounded", native.scheduler)
    monkeypatch.setattr(
        w,
        "_FixedRetiredDeletionNative",
        lambda plan: pytest.fail("constructed before matched reads"),
    )
    read, session = w.begin_fixed_retired_recovery_session()
    assert read.state is r.CleanupState.CONFLICTING and session is None


def test_recovery_starts_at_one_and_runs_every_original_remaining_target(partial):
    native, observation = partial
    canonical_before = {
        path: data
        for path, data in native.files.items()
        if path.startswith(r.CANONICAL_PATH + "\\")
    }
    operations = Operations(native, observation)
    native.calls.clear()
    result = op.run_recovery(operations)
    assert result.phase is r.CleanupPhase.PASS
    assert result.completed_targets == 337
    assert operations.backend.deleted_indices == list(range(1, 337))
    assert operations.post_calls == 1
    assert canonical_before == {
        path: data
        for path, data in native.files.items()
        if path.startswith(r.CANONICAL_PATH + "\\")
    }
    assert all(path != observation.plan.targets[0].path for _, path in native.calls)
    transcript = json.loads(result.canonical_transcript())
    assert transcript["operation"] == "P125-R1I"
    assert all(
        transcript[key] == "NONE"
        for key in ("activation_authority", "scheduler_authority", "trading_authority")
    )


@pytest.mark.parametrize(
    "failure,stage",
    [
        ("pre_call", "PRE_CALL"),
        ("native_false", "NATIVE_FALSE"),
        ("target_close", "TARGET_CLOSE_AMBIGUITY"),
        ("absence", "POST_CALL_VERIFY"),
        ("parent_inventory", "POST_CALL_VERIFY"),
        ("parent_identity", "POST_CALL_VERIFY"),
        ("parent_close", "PARENT_CLOSE_AMBIGUITY"),
        ("native_false_parent_close", "NATIVE_FALSE"),
    ],
)
def test_closed_stages_and_immediate_uint32_error_no_retry(
    partial, monkeypatch, failure, stage
):
    native, observation = partial
    operations = Operations(native, observation)
    backend = operations.backend
    backend.failure = failure

    def get_error():
        backend.events.append("get_last_error")
        return backend.last_error

    monkeypatch.setattr(ctypes, "get_last_error", get_error)
    result = op.run_recovery(operations)
    assert result.reason_code is r.CleanupBlockReason.INDETERMINATE_DELETE
    assert result.completed_targets == 1
    assert result.delete_diagnostic == r.DeleteDiagnostic(
        1, r.DeleteFailureStage(stage), 0xFFFFFFFF if stage == "NATIVE_FALSE" else None
    )
    assert backend.deleted_indices == [1]
    assert operations.post_calls == 0
    if stage == "NATIVE_FALSE":
        assert (
            backend.events[backend.events.index("disposition") + 1] == "get_last_error"
        )
        assert backend.last_error == 999
    else:
        assert "get_last_error" not in backend.events
    assert backend.events.count("target_close") == 1
    with pytest.raises(w.AdmissionBlocked):
        operations.session.delete_next()
    transcript = result.canonical_transcript()
    diagnostic = json.loads(transcript)["delete_diagnostic"]
    assert set(diagnostic) == {"target_index", "stage"} | (
        {"win32_error"} if stage == "NATIVE_FALSE" else set()
    )
    assert transcript == result.canonical_transcript()
    for forbidden in (b"raw exception", b"handle", b"ACL", b"environment", b"caller"):
        assert forbidden not in transcript


@pytest.mark.parametrize("code", [0, 5, 0xFFFFFFFF])
def test_native_false_uint32_contract(code):
    assert (
        r.DeleteDiagnostic(1, r.DeleteFailureStage.NATIVE_FALSE, code).win32_error
        == code
    )


@pytest.mark.parametrize("value", [-1, 0x100000000, True, False, "5", 5.0, None])
def test_native_false_rejects_untyped_unbounded_error(value):
    with pytest.raises(ValueError):
        r.DeleteDiagnostic(1, r.DeleteFailureStage.NATIVE_FALSE, value)


@pytest.mark.parametrize(
    "stage",
    [s for s in r.DeleteFailureStage if s is not r.DeleteFailureStage.NATIVE_FALSE],
)
def test_other_stages_cannot_carry_error(stage):
    with pytest.raises(ValueError):
        r.DeleteDiagnostic(1, stage, 5)


@pytest.mark.parametrize("index", [-1, 4096, True, "0", 0.0])
def test_diagnostic_target_index_is_closed(index):
    with pytest.raises(ValueError):
        r.DeleteDiagnostic(index, r.DeleteFailureStage.PRE_CALL)


def test_closed_diagnostic_attached_only_to_indeterminate_exact_target():
    assert {s.value for s in r.DeleteFailureStage} == {
        "PRE_CALL",
        "NATIVE_FALSE",
        "TARGET_CLOSE_AMBIGUITY",
        "POST_CALL_VERIFY",
        "PARENT_CLOSE_AMBIGUITY",
    }
    diagnostic = r.DeleteDiagnostic(1, r.DeleteFailureStage.PRE_CALL)
    result = r.CleanupResult(
        r.CleanupPhase.BLOCKED,
        r.CleanupState.PARTIAL_RETIRED,
        1,
        r.CleanupBlockReason.INDETERMINATE_DELETE,
        diagnostic,
    )
    for changed in (
        {"completed_targets": 2},
        {"reason_code": r.CleanupBlockReason.ADMISSION_FAILED},
        {"delete_diagnostic": "raw"},
        {"operation": "caller"},
    ):
        with pytest.raises(ValueError):
            replace(result, **changed)
    with pytest.raises(ValueError):
        r.CleanupResult(
            r.CleanupPhase.PASS,
            r.CleanupState.RETIRED_ABSENT,
            1,
            delete_diagnostic=diagnostic,
        )


def test_historical_r1e_transcripts_remain_byte_identical():
    for result, digest in (
        (
            r.CleanupResult(r.CleanupPhase.PASS, r.CleanupState.RETIRED_ABSENT),
            "99ba0e3356a5ebafaff9e6ca50f79b3a95f3f49c96d0d979239217a532b99ac8",
        ),
        (
            r.CleanupResult(
                r.CleanupPhase.BLOCKED,
                r.CleanupState.FULL_RETIRED,
                reason_code=r.CleanupBlockReason.INDETERMINATE_DELETE,
            ),
            "c5fb0b7e8b0d176daaeb9c134b9d7f02f53f824272f8c8e73005e970773aa0cd",
        ),
    ):
        assert _digest(result.canonical_transcript()) == digest
        assert "delete_diagnostic" not in json.loads(result.canonical_transcript())


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--execute-protected-p125-r1i"],
        ["--path", r.RETIRED_PATH],
        ["--target-index", "1"],
        ["--prefix-length", "1"],
        ["--kind", "file"],
        ["--scheduler", "D5"],
        ["--signing-identity", "v3"],
        ["--cleanup-mode", "partial"],
        ["--execute-protected-p125-r1e-cleanup"],
    ],
)
def test_cli_is_inert_and_accepts_no_other_authority(argv, monkeypatch):
    monkeypatch.setattr(
        w,
        "begin_fixed_retired_recovery_session",
        lambda: pytest.fail("native admission invoked"),
    )
    with pytest.raises(SystemExit):
        op.main(argv)


def test_exact_cli_dispatch_uses_only_recovery_seam(partial, monkeypatch):
    native, observation = partial
    operations = Operations(native, observation)
    monkeypatch.setattr(
        w,
        "begin_fixed_retired_recovery_session",
        operations.begin_fixed_retired_recovery_session,
    )
    monkeypatch.setattr(
        w, "observe_retired_cleanup_post", operations.observe_retired_cleanup_post
    )

    class Output:
        buffer = io.BytesIO()

    output = Output()
    monkeypatch.setattr(op.sys, "stdout", output)
    assert op.main(["--execute-protected-p125-r1i-retired-recovery"]) == 0
    assert json.loads(output.buffer.getvalue())["operation"] == "P125-R1I"


def test_operator_has_no_signing_activation_scheduler_provider_trading_surface():
    source = Path(op.__file__).read_text()
    tree = ast.parse(source)
    imports = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert set(imports) == {
        "__future__",
        "typing",
        "scripts",
        "scripts.p125_retire_old_d10",
    }
    for forbidden in (
        "signer",
        "activate",
        "broker",
        "provider",
        "paper",
        "live",
        "subprocess",
        "DeleteFileW",
        "RemoveDirectoryW",
        "shutil",
        "os.environ",
    ):
        assert forbidden not in source


@pytest.mark.parametrize("case", ["count", "first_path", "first_kind"])
def test_incident_plan_shape_rejects_wrong_count_first_path_or_kind(full, case):
    _, plan = full
    if case == "count":
        paths = plan.targets[:-1]
        # A valid historical cleanup plan with an extra directory still cannot
        # become the source-owned incident plan, even with the same first file.
        extra = r.RetiredCleanupTarget(r.RETIRED_PATH + r"\source\src\extra", True)
        source = r.RETIRED_PATH + r"\source\src"
        children = dict(plan.directory_children)
        children[source] = tuple(sorted((*children[source], "extra")))
        children[extra.path] = ()
        changed = r.RetiredCleanupPlan(
            (*paths, extra, plan.targets[-1]),
            tuple(sorted(children.items())),
            plan.manifest_sha256,
        )
    else:
        # Reorder a valid plan: the required first target must be the exact file.
        first = 1 if case == "first_path" else len(plan.targets) - 2
        targets = list(plan.targets)
        targets[0], targets[first] = targets[first], targets[0]
        changed = replace(plan, targets=tuple(targets))
    with pytest.raises(ValueError):
        r.require_retired_recovery_plan(changed)


def test_partial_missing_manifest_directory_uses_typed_absence_and_blocks(full):
    native, plan = full
    directory = next(
        target for target in plan.targets if target.directory and "p00" in target.path
    )
    for target in plan.targets:
        if target.path.startswith(directory.path + "\\"):
            native.remove(target.path)
    native.remove(directory.path)
    native.calls.clear()
    observed = native.observe()
    assert observed.state is r.CleanupState.PARTIAL_RETIRED
    assert ("absent_typed", directory.path) in native.calls
    assert ("absent", directory.path) not in native.calls
    with pytest.raises(w.AdmissionBlocked):
        w._require_retired_recovery(observed)


def test_success_commit_requires_exact_frozen_kind_for_file_and_directory(
    partial, monkeypatch
):
    native, observation = partial
    operations = Operations(native, observation)
    typed = operations.backend.absent_typed
    seen = []

    def checked(path, *, directory):
        assert directory is operations.backend._targets[path].directory
        seen.append(directory)
        return typed(path, directory=directory)

    monkeypatch.setattr(operations.backend, "absent_typed", checked)
    assert op.run_recovery(operations).phase is r.CleanupPhase.PASS
    assert False in seen and True in seen and len(seen) == 336


@pytest.mark.parametrize("result", [False, "exception"])
def test_final_two_read_proof_failure_blocks_after_exact_deletions(partial, result):
    native, observation = partial
    operations = Operations(native, observation)

    def post():
        if result == "exception":
            raise RuntimeError("private data")
        return False

    operations.observe_retired_cleanup_post = post
    stopped = op.run_recovery(operations)
    assert stopped.reason_code is r.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED
    assert stopped.completed_targets == 337
    assert stopped.delete_diagnostic is None
    assert operations.backend.deleted_indices == list(range(1, 337))


@pytest.mark.parametrize(
    "case",
    [
        "initial_zero",
        "initial_two",
        "initial_bool",
        "missing_extra",
        "indeterminate_exception",
        "success_without_progress",
    ],
)
def test_operator_rejects_false_session_evidence_and_never_retries(partial, case):
    native, observation = partial
    operations = Operations(native, observation)
    if case.startswith("initial_"):
        operations.session.completed_targets = {
            "initial_zero": 0,
            "initial_two": 2,
            "initial_bool": True,
        }[case]
    elif case == "missing_extra":
        operations.observation = replace(observation, missing_indices=(0, 1))
    else:
        calls = []

        def delete_next():
            calls.append(1)
            if case == "indeterminate_exception":
                raise RuntimeError("private exception")
            return r.MutationOutcome.SUCCESS

        operations.session.delete_next = delete_next
    result = op.run_recovery(operations)
    assert result.phase is r.CleanupPhase.BLOCKED
    assert operations.post_calls == 0
    assert operations.backend.deleted_indices == []
    if case in ("indeterminate_exception", "success_without_progress"):
        assert calls == [1]
        assert result.reason_code is r.CleanupBlockReason.INDETERMINATE_DELETE


@pytest.mark.parametrize(
    "state",
    [
        r.CleanupState.FULL_RETIRED,
        r.CleanupState.RETIRED_ABSENT,
        r.CleanupState.CONFLICTING,
    ],
)
def test_operator_rejects_every_other_retired_state(partial, state):
    native, observation = partial
    operations = Operations(native, observation)
    operations.observation = replace(observation, state=state)
    result = op.run_recovery(operations)
    assert result.phase is r.CleanupPhase.BLOCKED
    assert operations.backend.deleted_indices == [] and operations.post_calls == 0


@pytest.mark.parametrize("code", [0, 5, 0xFFFFFFFF, -1])
def test_native_false_captures_immediate_error_before_any_close(
    partial, monkeypatch, code
):
    native, observation = partial
    operations = Operations(native, observation)
    operations.backend.failure = "native_false"
    operations.backend.last_error = code
    monkeypatch.setattr(ctypes, "get_last_error", lambda: operations.backend.last_error)
    result = op.run_recovery(operations)
    assert result.delete_diagnostic.win32_error == code & 0xFFFFFFFF
    assert operations.backend.last_error == 999


@pytest.mark.parametrize("change", ["canonical", "scheduler", "parent", "missing"])
def test_final_proof_rechecks_every_invariant_twice(partial, change):
    native, observation = partial
    operations = Operations(native, observation)
    original = operations.observe_retired_cleanup_post
    native.calls.clear()

    def post():
        if change == "canonical":
            native.files[r.CANONICAL_PATH + r"\launch-guard.py"] += b"drift"
        elif change == "scheduler":
            native.scheduler_changes["enabled"] = False
        elif change == "parent":
            native.changes[r.PARENT_PATH] = {"aces": ()}
        else:
            calls_before = native.calls.count(("administrator", ""))
            assert original() is True
            assert native.calls.count(("administrator", "")) == calls_before + 2
            return False
        return original()

    operations.observe_retired_cleanup_post = post
    result = op.run_recovery(operations)
    assert result.reason_code is r.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED
    assert result.completed_targets == 337 and result.delete_diagnostic is None
